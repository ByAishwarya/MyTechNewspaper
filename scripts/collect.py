"""
Part 2, step 1: COLLECT.

Reads the sources in config/feeds.json, downloads each RSS feed, and turns every
item into ONE common format (the "article schema"):

    title, url, source, company, published_at, text,
    official, feed_name, feed_kind, collected_at

Output: data/raw/<YYYY-MM-DD>/articles_<HHMMSS>Z.jsonl   (one JSON object per line)
The raw files are never edited afterwards (later they go to S3 = raw archive).

Run from the project root with the virtual environment active:
    python scripts/collect.py
"""

import html
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "feeds.json"
RAW_DIR = ROOT / "data" / "raw"

# Be a polite client: say who we are, never wait forever, don't hammer one server.
USER_AGENT = "MyTechNewspaper/0.1 (student project; github.com/ByAishwarya/my-tech-newspaper)"
TIMEOUT_S = 15
PAUSE_BETWEEN_GOOGLE_REQUESTS_S = 1.0
TEXT_MAX_CHARS = 600  # we only need title + first paragraph for embeddings later


# ---------- small helpers ----------

def strip_html(value):
    """RSS summaries often contain HTML. Remove tags, decode &amp; etc., squash spaces."""
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def to_utc_iso(struct_time):
    """feedparser gives dates as time.struct_time already converted to UTC."""
    if not struct_time:
        return None
    return datetime(*struct_time[:6], tzinfo=timezone.utc).isoformat()


def fetch_feed(url):
    """Download with requests (timeout + User-Agent), then let feedparser parse the bytes."""
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"not a readable feed ({parsed.bozo_exception})")
    return parsed


def google_news_url(query, cfg):
    q = quote_plus(f"{query} when:{cfg['window']}")
    return f"https://news.google.com/rss/search?q={q}&hl={cfg['hl']}&gl={cfg['gl']}&ceid={cfg['ceid']}"


def entry_to_article(entry, *, feed_name, feed_kind, company, official, collected_at):
    """Map one RSS item (any feed) to our common schema."""
    title = strip_html(entry.get("title", ""))
    source = feed_name

    if feed_kind == "google_news":
        # Google News titles look like "Headline - Publisher"; the publisher is in <source>.
        publisher = (entry.get("source") or {}).get("title")
        if publisher:
            source = publisher
            suffix = f" - {publisher}"
            if title.endswith(suffix):
                title = title[: -len(suffix)].strip()

    return {
        "title": title,
        "url": entry.get("link", ""),
        "source": source,
        "company": company,
        "published_at": to_utc_iso(entry.get("published_parsed") or entry.get("updated_parsed")),
        "text": strip_html(entry.get("summary", ""))[:TEXT_MAX_CHARS],
        "official": official,
        "feed_name": feed_name,
        "feed_kind": feed_kind,
        "collected_at": collected_at,
    }


# ---------- main ----------

def main():
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    collected_at = now.isoformat(timespec="seconds")
    oldest_allowed = now - timedelta(hours=config["max_age_hours"])

    # Build one list of "jobs" so official feeds and Google News go through the same code.
    jobs = [
        {"name": f["name"], "url": f["url"], "company": f["company"], "official": True, "kind": "official"}
        for f in config["official_feeds"]
    ]
    gn = config["google_news"]
    jobs += [
        {"name": f"Google News: {q['company']}", "url": google_news_url(q["query"], gn),
         "company": q["company"], "official": False, "kind": "google_news"}
        for q in gn["queries"]
    ]

    articles, report = [], []
    for job in jobs:
        status = {"feed": job["name"], "ok": False, "items": 0, "kept": 0, "too_old": 0, "no_date": 0, "error": ""}
        try:
            parsed = fetch_feed(job["url"])
            status["ok"] = True
            status["items"] = len(parsed.entries)
            for entry in parsed.entries:
                art = entry_to_article(entry, feed_name=job["name"], feed_kind=job["kind"],
                                       company=job["company"], official=job["official"],
                                       collected_at=collected_at)
                if not art["title"] or not art["url"]:
                    continue
                if art["published_at"] is None:
                    status["no_date"] += 1      # keep it, but we can see how often this happens
                elif datetime.fromisoformat(art["published_at"]) < oldest_allowed:
                    status["too_old"] += 1
                    continue
                articles.append(art)
                status["kept"] += 1
        except Exception as exc:  # one broken feed must not stop the whole run
            status["error"] = f"{type(exc).__name__}: {exc}"[:80]
        report.append(status)
        if job["kind"] == "google_news":
            time.sleep(PAUSE_BETWEEN_GOOGLE_REQUESTS_S)

    # Save the raw archive (JSON Lines: easy to append, stream and load into pandas).
    out_dir = RAW_DIR / now.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"articles_{now.strftime('%H%M%S')}Z.jsonl"
    with out_file.open("w", encoding="utf-8") as fh:
        for art in articles:
            fh.write(json.dumps(art, ensure_ascii=False) + "\n")

    # ---------- quick look at the data with pandas ----------
    pd.set_option("display.width", 160)
    pd.set_option("display.max_colwidth", 70)

    print("\n=== Feed report ===")
    print(pd.DataFrame(report).to_string(index=False))

    if not articles:
        print("\nNo articles collected. Check the errors above (internet connection? blocked feed?).")
        return

    df = pd.DataFrame(articles)
    print(f"\nSaved {len(df)} articles to {out_file.relative_to(ROOT)}")

    print("\n=== Articles per company (official vs. coverage) ===")
    print(pd.crosstab(df["company"], df["official"].map({True: "official", False: "coverage"})))

    print("\n=== Data quality ===")
    print(f"missing published_at : {df['published_at'].isna().sum()}")
    print(f"empty text           : {(df['text'] == '').sum()}")
    print(f"median text length   : {int(df['text'].str.len().median())} chars")
    print(f"exact duplicate URLs : {df['url'].duplicated().sum()}   (step 2 will remove these)")
    print(f"duplicate titles     : {df['title'].str.lower().duplicated().sum()}")

    print("\n=== 10 newest articles ===")
    newest = df.sort_values("published_at", ascending=False).head(10)
    print(newest[["published_at", "company", "source", "title"]].to_string(index=False))


if __name__ == "__main__":
    main()

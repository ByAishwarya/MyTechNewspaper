"""
STEP 1 of the news engine: COLLECT

What it does
    Reads the sources in config/sources.json and collects two kinds of data:
      1. News ARTICLES from RSS feeds (official company feeds, topic feeds,
         Google News topic searches), all turned into ONE common schema.
      2. Product Hunt LAUNCHES of the last complete Product Hunt day
         (for the "Startup of the Day" card), via the official API.
    Articles and launches are different things, so they get different files.

Common article schema
    title, url, source, company, found_by, published_at, text,
    official, feed_name, feed_kind, collected_at

    company  = only filled when we KNOW it (official company feeds).
               Otherwise null: step 4 will extract it from the article itself.
    found_by = which feed or search query found the article (provenance).

Output (raw archive, never edited afterwards; later stored in S3)
    data/raw/<YYYY-MM-DD>/articles_<HHMMSS>Z.jsonl
    data/raw/<YYYY-MM-DD>/producthunt_<HHMMSS>Z.jsonl   (only if a token is set)

Next step
    scripts/step2_clean.py reads the newest articles file.

Run (project root, virtual environment active)
    python scripts/step1_collect.py
"""

import html
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import feedparser
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "sources.json"
RAW_DIR = ROOT / "data" / "raw"
load_dotenv(ROOT / ".env")

# Be a polite client: say who we are, never wait forever, don't hammer one server.
USER_AGENT = "MyTechNewspaper/0.2 (student project; github.com/ByAishwarya/my-tech-newspaper)"
TIMEOUT_S = 15
PAUSE_BETWEEN_GOOGLE_REQUESTS_S = 1.0
GOOGLE_NEWS_MAX_ITEMS = 100   # Google News never returns more than this per query
TEXT_MAX_CHARS = 600          # title + first paragraph is all we need for embeddings

PRODUCTHUNT_API = "https://api.producthunt.com/v2/api/graphql"
PRODUCTHUNT_TZ = ZoneInfo("America/Los_Angeles")   # a Product Hunt "day" runs on Pacific Time


# ---------------------------------------------------------------- helpers

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


def entry_to_article(entry, job, collected_at):
    """Map one RSS item (from any kind of feed) to our common schema."""
    title = strip_html(entry.get("title", ""))
    source = job["name"]

    if job["kind"] == "google_news":
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
        "company": job["company"],          # None unless the feed belongs to one company
        "found_by": job["found_by"],
        "published_at": to_utc_iso(entry.get("published_parsed") or entry.get("updated_parsed")),
        "text": strip_html(entry.get("summary", ""))[:TEXT_MAX_CHARS],
        "official": job["official"],
        "feed_name": job["name"],
        "feed_kind": job["kind"],
        "collected_at": collected_at,
    }


def build_jobs(config):
    """One list of feed jobs, so all three source types go through the same code."""
    jobs = [
        {"name": f["name"], "url": f["url"], "company": f["company"], "official": True,
         "kind": "official", "found_by": f["name"]}
        for f in config["official_feeds"]
    ]
    jobs += [
        {"name": f["name"], "url": f["url"], "company": None, "official": False,
         "kind": "topic_feed", "found_by": f["name"]}
        for f in config["topic_feeds"]
    ]
    gn = config["google_news"]
    jobs += [
        {"name": f"Google News: {q['label']}", "url": google_news_url(q["query"], gn),
         "company": None, "official": False, "kind": "google_news", "found_by": q["label"]}
        for q in gn["queries"]
    ]
    return jobs


# ---------------------------------------------------------------- articles

def collect_articles(config, now, collected_at):
    oldest_allowed = now - timedelta(hours=config["max_age_hours"])
    articles, report = [], []

    for job in build_jobs(config):
        status = {"feed": job["name"], "kind": job["kind"], "ok": False, "items": 0, "kept": 0,
                  "too_old": 0, "no_date": 0, "capped": False, "error": ""}
        try:
            parsed = fetch_feed(job["url"])
            status["ok"] = True
            status["items"] = len(parsed.entries)
            # Hitting the maximum means Google probably had MORE articles that we never saw.
            status["capped"] = job["kind"] == "google_news" and status["items"] >= GOOGLE_NEWS_MAX_ITEMS
            for entry in parsed.entries:
                art = entry_to_article(entry, job, collected_at)
                if not art["title"] or not art["url"]:
                    continue
                if art["published_at"] is None:
                    status["no_date"] += 1      # keep it, but make the problem visible
                elif datetime.fromisoformat(art["published_at"]) < oldest_allowed:
                    status["too_old"] += 1
                    continue
                articles.append(art)
                status["kept"] += 1
        except Exception as exc:  # one broken source must not stop the whole run
            status["error"] = f"{type(exc).__name__}: {exc}"[:80]
        report.append(status)
        if job["kind"] == "google_news":
            time.sleep(PAUSE_BETWEEN_GOOGLE_REQUESTS_S)

    return articles, report


# ---------------------------------------------------------------- Product Hunt

PRODUCTHUNT_QUERY = """
query TopLaunches($after: DateTime!, $before: DateTime!, $first: Int!) {
  posts(featured: true, order: VOTES, postedAfter: $after, postedBefore: $before, first: $first) {
    edges {
      node {
        id name tagline description url website votesCount commentsCount createdAt
        topics(first: 5) { edges { node { name } } }
      }
    }
  }
}
"""


def last_complete_producthunt_day(now):
    """
    Our run is at about 06:00 Berlin time = about 21:00 the PREVIOUS day in California.
    So "today" on Product Hunt is not finished yet. We take the last COMPLETE day.
    """
    today_pt = now.astimezone(PRODUCTHUNT_TZ).date()
    day = today_pt - timedelta(days=1)
    start = datetime.combine(day, datetime.min.time(), tzinfo=PRODUCTHUNT_TZ)
    end = datetime.combine(today_pt, datetime.min.time(), tzinfo=PRODUCTHUNT_TZ)
    return day, start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def collect_producthunt(config, now, collected_at):
    cfg = config["producthunt"]
    status = {"feed": "Product Hunt API", "kind": "producthunt", "ok": False, "items": 0,
              "kept": 0, "too_old": 0, "no_date": 0, "capped": False, "error": ""}
    token = os.getenv("PRODUCTHUNT_TOKEN", "").strip()
    if not cfg.get("enabled", True):
        status["error"] = "disabled in config"
        return [], status
    if not token:
        status["error"] = "no PRODUCTHUNT_TOKEN in .env (skipped)"
        return [], status

    day, start, end = last_complete_producthunt_day(now)
    try:
        response = requests.post(
            PRODUCTHUNT_API,
            json={"query": PRODUCTHUNT_QUERY,
                  "variables": {"after": start.isoformat(), "before": end.isoformat(),
                                "first": cfg["top_n"]}},
            headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT,
                     "Accept": "application/json"},
            timeout=TIMEOUT_S,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):   # GraphQL reports errors INSIDE a 200 response
            raise ValueError(payload["errors"][0].get("message", "GraphQL error"))

        launches = []
        for rank, edge in enumerate(payload["data"]["posts"]["edges"], start=1):
            node = edge["node"]
            launches.append({
                "producthunt_day": day.isoformat(),
                "rank_by_votes": rank,
                "name": node["name"],
                "tagline": node.get("tagline") or "",
                "description": (node.get("description") or "")[:TEXT_MAX_CHARS],
                "producthunt_url": node.get("url"),
                "website": node.get("website"),
                "votes": node.get("votesCount"),
                "comments": node.get("commentsCount"),
                "topics": [t["node"]["name"] for t in node["topics"]["edges"]],
                "created_at": node.get("createdAt"),
                "collected_at": collected_at,
            })
        status.update(ok=True, items=len(launches), kept=len(launches))
        return launches, status
    except Exception as exc:
        status["error"] = f"{type(exc).__name__}: {exc}"[:80]
        return [], status


# ---------------------------------------------------------------- main

def write_jsonl(path, rows):
    """JSON Lines: one JSON object per line. Easy to append, stream and load into pandas."""
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    collected_at = now.isoformat(timespec="seconds")

    articles, report = collect_articles(config, now, collected_at)
    launches, ph_status = collect_producthunt(config, now, collected_at)
    report.append(ph_status)

    out_dir = RAW_DIR / now.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%H%M%S")
    articles_file = out_dir / f"articles_{stamp}Z.jsonl"
    write_jsonl(articles_file, articles)
    if launches:
        write_jsonl(out_dir / f"producthunt_{stamp}Z.jsonl", launches)

    # ------------------------------------------------ quick look with pandas
    pd.set_option("display.width", 160)
    pd.set_option("display.max_colwidth", 60)

    print("\n=== Source report ===")
    print(pd.DataFrame(report).to_string(index=False))

    if not articles:
        print("\nNo articles collected. Check the errors above (internet connection? blocked feed?).")
        return

    df = pd.DataFrame(articles)
    print(f"\nSaved {len(df)} articles to {articles_file.relative_to(ROOT)}")

    print("\n=== Articles per source type ===")
    print(df["feed_kind"].value_counts().to_string())

    print("\n=== Top 10 publishers (noise check: are these launches or stock tips?) ===")
    print(df["source"].value_counts().head(10).to_string())

    print("\n=== Data quality ===")
    print(f"missing published_at : {df['published_at'].isna().sum()}")
    print(f"company known        : {df['company'].notna().sum()} of {len(df)} (rest: step 4 extracts it)")
    print(f"median text length   : {int(df['text'].str.len().median())} chars")
    print(f"exact duplicate URLs : {df['url'].duplicated().sum()}   (step 2 removes these)")
    print(f"duplicate titles     : {df['title'].str.lower().duplicated().sum()}")
    capped = [r["feed"] for r in report if r["capped"]]
    if capped:
        print(f"capped at {GOOGLE_NEWS_MAX_ITEMS} (we missed articles): {', '.join(capped)}")

    if launches:
        print(f"\n=== Product Hunt: top launches of {launches[0]['producthunt_day']} (Pacific Time) ===")
        ph = pd.DataFrame(launches)[["rank_by_votes", "name", "votes", "tagline"]]
        print(ph.to_string(index=False))


if __name__ == "__main__":
    main()

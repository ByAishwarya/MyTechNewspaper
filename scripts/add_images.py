"""
add_images.py: prototype of the image step (n8n will do the same in Part 2).

For each story in data/editions/latest.json it tries, in order:
  1. The official source page's preview image (<meta property="og:image">)
  2. A Pexels stock photo that matches the story category
  3. Nothing: image = None, and the website shows the coloured tile

Run it from the project root:
    python scripts/add_images.py

It needs a free Pexels API key in a file called .env in the project root:
    PEXELS_API_KEY=your-key-here
"""

import json
import os
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
EDITION_FILE = ROOT / "data" / "editions" / "latest.json"

load_dotenv(ROOT / ".env")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

HEADERS = {"User-Agent": "MyTechNewspaper/0.1 (student project)"}
TIMEOUT_SECONDS = 10

# What to search on Pexels for each story category.
# Searching "Nvidia" would return random photos, so we search the topic instead.
CATEGORY_QUERIES = {
    "product_launch": "technology product launch",
    "ai_model": "artificial intelligence",
    "pricing": "online payment",
    "partnership": "business handshake",
    "funding": "startup office",
    "leadership": "business meeting",
    "regulation": "european union flag",
    "other": "technology",
}


# ---------- Step 1: og:image from the official page ----------

class OgImageFinder(HTMLParser):
    """Reads HTML and remembers the first og:image (or twitter:image) it sees."""

    def __init__(self):
        super().__init__()
        self.image_url = None

    def handle_starttag(self, tag, attrs):
        if tag != "meta" or self.image_url:
            return
        a = dict(attrs)
        key = (a.get("property") or a.get("name") or "").lower()
        if key in ("og:image", "og:image:url", "og:image:secure_url", "twitter:image") and a.get("content"):
            self.image_url = a["content"].strip()


def find_og_image(page_url):
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"    og:image: page not reachable ({error.__class__.__name__})")
        return None

    finder = OgImageFinder()
    finder.feed(response.text[:500_000])  # the <head> is at the top; no need to read huge pages
    if not finder.image_url:
        print("    og:image: page has no preview image")
        return None

    image_url = urljoin(page_url, finder.image_url)  # turns "/img/a.jpg" into a full URL
    if not image_url.startswith("https://"):
        print("    og:image: not https, skipped")
        return None
    return image_url


# ---------- Step 2: Pexels stock photo ----------

def find_pexels_photo(query, used_photo_ids):
    if not PEXELS_API_KEY:
        print("    Pexels: no PEXELS_API_KEY in .env, skipped")
        return None
    try:
        response = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "orientation": "landscape", "per_page": 15},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"    Pexels: request failed ({error.__class__.__name__})")
        return None

    for photo in response.json().get("photos", []):
        if photo["id"] in used_photo_ids:
            continue  # avoid showing the same photo on two cards
        used_photo_ids.add(photo["id"])
        return {
            "url": photo["src"]["landscape"],
            "source": "pexels",
            "credit_name": photo["photographer"],
            "credit_url": photo["photographer_url"],
            "provider_name": "Pexels",
            "provider_url": "https://www.pexels.com",
            "page_url": photo["url"],
        }
    print("    Pexels: no unused photo found")
    return None


# ---------- Main ----------

def main():
    edition = json.loads(EDITION_FILE.read_text(encoding="utf-8"))
    used_photo_ids = set()
    counts = {"official": 0, "pexels": 0, "tile": 0}

    for story in edition["stories"]:
        print(f"#{story['rank']} {story['company']}")
        official = next((s for s in story["sources"] if s.get("official")), None)

        image = None
        if official:
            og_url = find_og_image(official["url"])
            if og_url:
                image = {
                    "url": og_url,
                    "source": "official",
                    "credit_name": story["company"],
                    "credit_url": official["url"],
                }
        if image is None:
            query = CATEGORY_QUERIES.get(story["category"], CATEGORY_QUERIES["other"])
            image = find_pexels_photo(query, used_photo_ids)

        story["image"] = image
        story.pop("image_url", None)  # old field name from Part 1
        kind = image["source"] if image else "tile"
        counts[kind] += 1
        print(f"    -> {kind}")

    EDITION_FILE.write_text(json.dumps(edition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nDone: {counts['official']} official, {counts['pexels']} Pexels, {counts['tile']} coloured tiles.")
    print(f"Saved to {EDITION_FILE}")


if __name__ == "__main__":
    main()

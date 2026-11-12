"""
add_images.py: prototype of the image step (n8n will do the same in Part 2).

For each story in data/editions/latest.json it tries, in order:
  1. The official source page's preview image (<meta property="og:image">)
  2. A Pixabay stock photo that matches the story category
  3. Nothing: image = None, and the website shows the coloured tile

Pixabay rules this script follows (https://pixabay.com/api/docs/):
  - No permanent hotlinking: photos are DOWNLOADED to data/images/
    (later: uploaded to S3) and the website loads them from there.
  - Search results are cached for 24 hours (data/cache/).
  - The website shows where the photos come from (credit + footer).

Run it from the project root:
    python scripts/add_images.py

It needs a free Pixabay API key in a file called .env in the project root:
    PIXABAY_API_KEY=your-key-here
"""

import json
import os
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
EDITION_FILE = ROOT / "data" / "editions" / "latest.json"
IMAGES_DIR = ROOT / "data" / "images"   # downloaded photos (later: S3)
CACHE_DIR = ROOT / "data" / "cache"     # Pixabay search results, kept 24 hours
CACHE_SECONDS = 24 * 60 * 60

# How the website (frontend/index.html) reaches the images folder.
IMAGE_URL_PREFIX = "../data/images/"

load_dotenv(ROOT / ".env")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

HEADERS = {"User-Agent": "MyTechNewspaper/0.1 (student project)"}
TIMEOUT_SECONDS = 10

# What to search for each story category.
# Searching "Nvidia" would return random photos, so we search the topic instead.
CATEGORY_QUERIES = {
    "product_launch": "technology product",
    "ai_model": "artificial intelligence",
    "pricing": "online payment",
    "partnership": "business handshake",
    "funding": "startup office",
    "leadership": "business meeting",
    "regulation": "european union",
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


# ---------- Step 2: Pixabay stock photo ----------

def search_pixabay(query):
    """Returns Pixabay search results, using a 24-hour cache as Pixabay requires."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"pixabay_{query.replace(' ', '_')}.json"

    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_SECONDS:
        return json.loads(cache_file.read_text(encoding="utf-8"))

    try:
        response = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": PIXABAY_API_KEY,
                "q": query,
                "image_type": "photo",
                "orientation": "horizontal",
                "safesearch": "true",
                "per_page": 30,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"    Pixabay: search failed ({error.__class__.__name__})")
        return []

    hits = response.json().get("hits", [])
    cache_file.write_text(json.dumps(hits), encoding="utf-8")
    return hits


def download_image(image_url, photo_id):
    """Saves the photo to data/images/ and returns the file name, or None.
    A photo that is already saved is not downloaded again."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    extension = Path(urlparse(image_url).path).suffix.lower() or ".jpg"
    file_name = f"pixabay_{photo_id}{extension}"
    target = IMAGES_DIR / file_name
    if target.exists():
        return file_name
    try:
        response = requests.get(image_url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"    Pixabay: download failed ({error.__class__.__name__})")
        return None
    if not response.headers.get("Content-Type", "").startswith("image/"):
        print("    Pixabay: download was not an image")
        return None
    target.write_bytes(response.content)
    return file_name


def find_pixabay_photo(query, used_photo_ids):
    if not PIXABAY_API_KEY:
        print("    Pixabay: no PIXABAY_API_KEY in .env, skipped")
        return None

    for hit in search_pixabay(query):
        if hit["id"] in used_photo_ids:
            continue  # avoid showing the same photo on two cards
        file_name = download_image(hit["webformatURL"], hit["id"])
        if not file_name:
            continue
        used_photo_ids.add(hit["id"])
        return {
            "url": IMAGE_URL_PREFIX + file_name,
            "source": "pixabay",
            "credit_name": hit["user"],
            "credit_url": f"https://pixabay.com/users/{hit['user']}-{hit['user_id']}/",
            "provider_name": "Pixabay",
            "provider_url": "https://pixabay.com",
            "page_url": hit["pageURL"],
        }
    print("    Pixabay: no unused photo found")
    return None


# ---------- Main ----------

def main():
    edition = json.loads(EDITION_FILE.read_text(encoding="utf-8"))
    used_photo_ids = set()
    counts = {"official": 0, "pixabay": 0, "tile": 0}

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
            image = find_pixabay_photo(query, used_photo_ids)

        story["image"] = image
        story.pop("image_url", None)  # old field name from Part 1
        kind = image["source"] if image else "tile"
        counts[kind] += 1
        print(f"    -> {kind}")

    EDITION_FILE.write_text(json.dumps(edition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nDone: {counts['official']} official, {counts['pixabay']} Pixabay, {counts['tile']} coloured tiles.")
    print(f"Saved to {EDITION_FILE}")


if __name__ == "__main__":
    main()

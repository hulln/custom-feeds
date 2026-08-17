#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SOURCE_URL = "https://www.uni-lj.si/studij/center-digitalna-ul/gradiva/namigi-in-triki/aktualno-dogajanje-na-podrocju-ui-v-izobrazevanju"
BASE_URL = "https://www.uni-lj.si"
FEED_URL = "https://raw.githubusercontent.com/hulln/custom-feeds/main/digitalna-ul/feed.json"
OUTPUT = Path(__file__).with_name("feed.json")
ITEM_LIMIT = 30
USER_AGENT = "CustomFeeds/1.0 (+https://github.com/hulln/custom-feeds)"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href and "/novice/" in href:
                self._href = href
                self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            text = " ".join("".join(self._text).split())
            if text and text.lower() != "preberi več":
                self.links.append((urljoin(BASE_URL, self._href), text))
            self._href = None
            self._text = []


class MainTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.in_main = False
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "main":
            self.in_main = True
            self.depth = 1
            return
        if self.in_main:
            self.depth += 1
            if tag in {"script", "style", "nav", "footer", "header", "svg"}:
                self.skip_depth += 1
            if tag in {"p", "h1", "h2", "h3", "li", "br"} and not self.skip_depth:
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if not self.in_main:
            return
        tag = tag.lower()
        if self.skip_depth and tag in {"script", "style", "nav", "footer", "header", "svg"}:
            self.skip_depth -= 1
        self.depth -= 1
        if self.depth <= 0:
            self.in_main = False

    def handle_data(self, data):
        if self.in_main and not self.skip_depth:
            text = " ".join(data.split())
            if text:
                self.parts.append(text + " ")

    def text(self):
        text = "".join(self.parts)
        lines = [" ".join(line.split()) for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n\n".join(lines)


def fetch(url: str, retries: int = 3) -> str:
    last_exc = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
            with urlopen(req, timeout=30) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise last_exc


def extract_date(url: str) -> str | None:
    m = re.search(r"/novice/(\d{4})-(\d{2})-(\d{2})-", url)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    return datetime(y, mo, d, 12, 0, tzinfo=timezone.utc).isoformat()


def article_text(url: str) -> str:
    page = fetch(url)
    parser = MainTextParser()
    parser.feed(page)
    text = parser.text()
    for marker in ["Drobtinice", "Hitre povezave", "Kontakt", "Družbena omrežja"]:
        pos = text.find(marker)
        if pos > 500:
            text = text[:pos].rstrip()
    return text[:20000].rstrip()


def main() -> None:
    page = fetch(SOURCE_URL)
    parser = LinkParser()
    parser.feed(page)

    seen = set()
    links: list[tuple[str, str]] = []
    for url, title in parser.links:
        if url in seen:
            continue
        seen.add(url)
        links.append((url, title))

    links = links[:ITEM_LIMIT]
    if not links:
        raise SystemExit("No Digitalna UL newsletter links found")

    items = []
    for url, title in links:
        try:
            content = article_text(url)
        except Exception as exc:
            print(f"warning: cannot fetch {url}: {exc}")
            content = title
        item = {"id": url, "url": url, "title": title, "content_text": content or title}
        date = extract_date(url)
        if date:
            item["date_published"] = date
        items.append(item)

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Center Digitalna UL – UI-novičniki",
        "home_page_url": SOURCE_URL,
        "feed_url": FEED_URL,
        "description": "Neuradni JSON Feed za UI-novičnike Centra Digitalna UL.",
        "language": "sl",
        "items": items,
    }
    OUTPUT.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUTPUT}")


if __name__ == "__main__":
    main()

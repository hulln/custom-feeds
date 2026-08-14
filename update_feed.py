#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ARCHIVE_ROOT = "https://mailman.ijs.si/pipermail/slovlit/"
FEED_URL = "https://raw.githubusercontent.com/hulln/slovlit-rss/main/feed.xml"
SITE_URL = "https://mailman.ijs.si/pipermail/slovlit/"
ITEM_LIMIT = 30
USER_AGENT = "SlovLit-RSS/1.0 (+https://github.com/hulln/slovlit-rss)"
OUTPUT = Path(__file__).with_name("feed.xml")

ATOM_NS = "http://www.w3.org/2005/Atom"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("content", CONTENT_NS)

@dataclass(frozen=True)
class ArchiveItem:
    title: str
    url: str

class ArchiveIndexParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items: list[ArchiveItem] = []
        self._href: str | None = None
        self._text: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href and re.search(r"(?:^|/)\d{6}\.html$", href):
            self._href, self._text = href, []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            title = " ".join("".join(self._text).split())
            if title:
                self.items.append(ArchiveItem(title, urljoin(self.base_url, self._href)))
            self._href, self._text = None, []

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def text(self):
        return "\n".join(line.rstrip() for line in "".join(self.parts).splitlines()).strip()

def fetch(url, retries=3):
    last_exc = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
            with urlopen(req, timeout=30) as response:
                raw = response.read()
                charset = response.headers.get_content_charset()
                return decode(raw, charset), charset
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise last_exc

def decode(raw, charset=None):
    for enc in [charset, "utf-8", "iso-8859-2", "windows-1250", "latin-1"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            pass
    return raw.decode("utf-8", errors="replace")

def current_items():
    now = datetime.now(timezone.utc)
    all_items = []
    for year in [now.year - 1, now.year]:
        index_url = f"{ARCHIVE_ROOT}{year}/date.html"
        try:
            page, _ = fetch(index_url)
        except Exception as exc:
            print(f"warning: cannot fetch {index_url}: {exc}", file=sys.stderr)
            continue
        parser = ArchiveIndexParser(index_url)
        parser.feed(page)
        all_items.extend(parser.items)
    items = list({i.url: i for i in all_items}.values())
    items.sort(key=lambda i: int(re.search(r"(\d{6})\.html$", i.url).group(1)))
    return items[-ITEM_LIMIT:]

def article_text(page):
    match = re.search(r"<!--\s*beginarticle\s*-->(.*?)<!--\s*endarticle\s*-->", page, flags=re.I | re.S)
    if not match:
        return ""
    extractor = TextExtractor()
    extractor.feed(match.group(1))
    text = extractor.text()
    return text[:10000].rstrip() + "…" if len(text) > 10000 else text

def load_existing():
    if not OUTPUT.exists():
        return {}
    try:
        root = ET.parse(OUTPUT).getroot()
    except ET.ParseError:
        return {}
    result = {}
    channel = root.find("channel")
    if channel is None:
        return result
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        if link:
            result[link] = {
                "description": item.findtext("description") or "",
                "pubDate": item.findtext("pubDate") or "",
            }
    return result

def normalize_pubdate(pubdate: str) -> str:
    month_map = {
        "Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr", "May": "May", "Maj": "May",
        "Jun": "Jun", "Jul": "Jul", "Aug": "Aug", "Avg": "Aug", "Sep": "Sep", "Okt": "Oct",
        "Oct": "Oct", "Nov": "Nov", "Dec": "Dec",
    }
    m = re.match(r"^(\d{2})\s+([A-Za-zČŠŽčšž]{3})\s+(\d{4})\s+(\d{2}:\d{2}:\d{2})\s+([+-]\d{4})$", pubdate)
    if not m:
        return pubdate
    day, month, year, clock, offset = m.groups()
    return f"{day} {month_map.get(month, month)} {year} {clock} {offset}"

def extract_pubdate(page):
    match = re.search(r"<i[^>]*>(.*?)</i>", page, flags=re.I | re.S)
    if not match:
        return ""
    text = html.unescape(" ".join(re.sub(r"<[^>]+>", " ", match.group(1)).split()))
    day_map = {
        "Pon": "Mon", "Tor": "Tue", "Sre": "Wed", "Čet": "Thu", "Cet": "Thu",
        "Pet": "Fri", "Sob": "Sat", "Ned": "Sun",
    }
    month_map = {
        "Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr", "Maj": "May", "May": "May",
        "Jun": "Jun", "Jul": "Jul", "Avg": "Aug", "Aug": "Aug", "Sep": "Sep",
        "Okt": "Oct", "Oct": "Oct", "Nov": "Nov", "Dec": "Dec",
    }
    parts = text.split(" ", 1)
    if parts and parts[0] in day_map:
        text = day_map[parts[0]] + (" " + parts[1] if len(parts) > 1 else "")
    m = re.match(r"^[A-Za-z]{3}\s+([A-Za-zČŠŽčšž]{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s+([A-Z]{2,5})\s+(\d{4})$", text)
    if not m:
        return ""
    month, day, hh, mm, ss, zone, year = m.groups()
    month = month_map.get(month, month)
    offset = {"CET": "+0100", "CEST": "+0200", "UTC": "+0000", "GMT": "+0000"}.get(zone, "+0000")
    return f"{day.zfill(2)} {month} {year} {hh}:{mm}:{ss} {offset}"

def stable_guid(url: str) -> str:
    msg_id = re.search(r"(\d{6})\.html$", url)
    suffix = msg_id.group(1) if msg_id else url
    return f"urn:slovlit:{suffix}:fulltext-v2"

def build_feed(items):
    existing = load_existing()
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    for tag, text in [
        ("title", "SlovLit"),
        ("link", SITE_URL),
        ("description", "Neuradni RSS za javni arhiv poštnega seznama SlovLit."),
        ("language", "sl"),
        ("lastBuildDate", format_datetime(datetime.now(timezone.utc))),
        ("generator", "SlovLit RSS generator"),
    ]:
        ET.SubElement(channel, tag).text = text
    ET.SubElement(channel, f"{{{ATOM_NS}}}link", {
        "href": FEED_URL,
        "rel": "self",
        "type": "application/rss+xml",
    })

    for archive_item in reversed(items):
        cached = existing.get(archive_item.url, {})
        description = cached.get("description", "")
        pubdate = normalize_pubdate(cached.get("pubDate", ""))
        if not description or not pubdate:
            try:
                page, _ = fetch(archive_item.url)
                if not description:
                    description = article_text(page)
                if not pubdate:
                    pubdate = extract_pubdate(page)
            except Exception as exc:
                print(f"warning: cannot fetch {archive_item.url}: {exc}", file=sys.stderr)

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = archive_item.title
        ET.SubElement(item, "link").text = archive_item.url
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = stable_guid(archive_item.url)
        if pubdate:
            ET.SubElement(item, "pubDate").text = pubdate
        if description:
            ET.SubElement(item, "description").text = description
            ET.SubElement(item, f"{{{CONTENT_NS}}}encoded").text = description

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(OUTPUT, encoding="utf-8", xml_declaration=True)

def main():
    items = current_items()
    if not items:
        raise SystemExit("No SlovLit archive items found; refusing to overwrite the feed.")
    build_feed(items)
    print(f"Wrote {len(items)} items to {OUTPUT}")

if __name__ == "__main__":
    main()

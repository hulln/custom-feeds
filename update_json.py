#!/usr/bin/env python3
import json
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
XML_PATH = ROOT / "feed.xml"
JSON_PATH = ROOT / "feed.json"


def to_iso(value: str) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return None


def main() -> None:
    root = ET.parse(XML_PATH).getroot()
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("RSS channel not found")

    items = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or url).strip()
        content = item.findtext("description") or ""
        pubdate = to_iso(item.findtext("pubDate") or "")

        obj = {
            "id": guid,
            "url": url,
            "title": title,
            "content_text": content,
        }
        if pubdate:
            obj["date_published"] = pubdate
        items.append(obj)

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "SlovLit",
        "home_page_url": "https://mailman.ijs.si/pipermail/slovlit/",
        "feed_url": "https://raw.githubusercontent.com/hulln/slovlit-rss/main/feed.json",
        "description": "Neuradni polnobesedilni feed za javni arhiv poštnega seznama SlovLit.",
        "language": "sl",
        "items": items,
    }
    JSON_PATH.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} items to {JSON_PATH}")


if __name__ == "__main__":
    main()

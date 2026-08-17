#!/usr/bin/env python3
import html
import json
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).parent
XML_PATH = ROOT / "feed.xml"
JSON_PATH = ROOT / "feed.json"

HEADER_RE = re.compile(
    r"^(From|Od|To|Za|Date|Datum|Poslano|Sent|Subject|Zadeva):\s*(.*)$",
    re.IGNORECASE,
)
SEPARATOR_RE = re.compile(r"^\s*={3,}\s*$")
URL_RE = re.compile(r"(https?://[^\s<]+)")

LABELS = {
    "from": "Od",
    "od": "Od",
    "to": "Za",
    "za": "Za",
    "date": "Datum",
    "datum": "Datum",
    "poslano": "Datum",
    "sent": "Datum",
    "subject": "Zadeva",
    "zadeva": "Zadeva",
}


def to_iso(value: str) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return None


def linkify(text: str) -> str:
    escaped = html.escape(text, quote=False)

    def repl(match: re.Match) -> str:
        url = match.group(1)
        trailing = ""
        while url and url[-1] in ".,;:!?)]}":
            trailing = url[-1] + trailing
            url = url[:-1]
        return f'<a href="{html.escape(url, quote=True)}">{url}</a>{trailing}'

    return URL_RE.sub(repl, escaped)


def normalise_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]


def render_headers(lines: list[str], start: int) -> tuple[str, int]:
    headers: list[tuple[str, str]] = []
    i = start
    while i < len(lines):
        match = HEADER_RE.match(lines[i].strip())
        if not match:
            break
        raw_label, value = match.groups()
        label = LABELS.get(raw_label.lower(), raw_label)
        value_parts = [value.strip()] if value.strip() else []
        i += 1
        while i < len(lines):
            current = lines[i]
            if not current.strip() or HEADER_RE.match(current.strip()) or SEPARATOR_RE.match(current):
                break
            value_parts.append(current.strip())
            i += 1
        headers.append((label, " ".join(value_parts).strip()))
        if i < len(lines) and not lines[i].strip():
            break
    rows = [f"<strong>{html.escape(label)}:</strong> {linkify(value)}" for label, value in headers]
    return "<p>" + "<br>\n".join(rows) + "</p>", i


def render_body_paragraph(lines: list[str], start: int) -> tuple[str, int]:
    parts: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or SEPARATOR_RE.match(line) or HEADER_RE.match(stripped):
            break
        parts.append(stripped)
        i += 1
    return f"<p>{linkify(' '.join(parts))}</p>", i


def format_slovlit_html(text: str) -> str:
    lines = normalise_lines(text)
    out: list[str] = []
    i = 0
    has_content = False
    just_separated = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if SEPARATOR_RE.match(line):
            if has_content and not just_separated:
                out.append("<hr>")
                just_separated = True
            i += 1
            continue
        if HEADER_RE.match(stripped):
            label = HEADER_RE.match(stripped).group(1).lower()
            if label in {"from", "od"} and has_content and not just_separated:
                out.append("<hr>")
            header_html, i = render_headers(lines, i)
            out.append(header_html)
            has_content = True
            just_separated = False
            continue
        paragraph_html, i = render_body_paragraph(lines, i)
        if paragraph_html != "<p></p>":
            out.append(paragraph_html)
            has_content = True
            just_separated = False
    while out and out[-1] == "<hr>":
        out.pop()
    return "\n".join(out)


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
            "content_html": format_slovlit_html(content),
        }
        if pubdate:
            obj["date_published"] = pubdate
        items.append(obj)

    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "SlovLit",
        "home_page_url": "https://mailman.ijs.si/pipermail/slovlit/",
        "feed_url": "https://raw.githubusercontent.com/hulln/custom-feeds/main/feed.json",
        "description": "Neuradni polnobesedilni feed za javni arhiv poštnega seznama SlovLit.",
        "language": "sl",
        "items": items,
    }
    JSON_PATH.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} items to {JSON_PATH}")


if __name__ == "__main__":
    main()

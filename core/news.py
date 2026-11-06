"""Live news lookup through Google News RSS (no API key needed).

The "adverse-media" mode adds the financial-crime keywords an AML analyst
would use in a manual negative-news search.
"""
from __future__ import annotations

import email.utils
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import requests

RSS_URL = "https://news.google.com/rss/search?q={q}&hl=en-IE&gl=IE&ceid=IE:en"
ADVERSE_TERMS = ["fraud", "laundering", "sanctions", "bribery", "corruption", "investigation",
                 "fine", "lawsuit", "charged", "probe", "embezzlement", "money laundering"]
WINDOWS = {"Any time": None, "Past day": "1d", "Past week": "7d", "Past month": "30d", "Past year": "1y"}


def build_query(term: str, adverse: bool = False, window: str | None = None) -> str:
    q = f'"{term.strip()}"' if " " in term.strip() else term.strip()
    if adverse:
        q += " (" + " OR ".join(t if " " not in t else f'"{t}"' for t in ADVERSE_TERMS[:9]) + ")"
    if window:
        q += f" when:{window}"
    return q


def parse_rss(xml_text: str, limit: int = 30) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source_el = item.find("source")
        source = (source_el.text or "").strip() if source_el is not None else ""
        if source and title.endswith(f" - {source}"):  # Google appends " - Publisher" to titles
            title = title[: -len(source) - 3]
        published = None
        if item.findtext("pubDate"):
            try:
                published = email.utils.parsedate_to_datetime(item.findtext("pubDate")).isoformat()
            except (TypeError, ValueError):
                published = None
        out.append({"title": title, "link": item.findtext("link"), "publisher": source, "published": published})
        if len(out) >= limit:
            break
    return out


def search(term: str, adverse: bool = False, window: str | None = None, limit: int = 30) -> tuple[list[dict], bool]:
    """Returns (items, is_demo). Falls back to fictional demo items when offline."""
    if not term.strip():
        return [], False
    try:
        r = requests.get(RSS_URL.format(q=quote_plus(build_query(term, adverse, window))), timeout=10,
                         headers={"User-Agent": "Mozilla/5.0 (FinRisk Lab, educational project)"})
        r.raise_for_status()
        return parse_rss(r.text, limit), False
    except Exception:  # noqa: BLE001
        from samples import SNIPPETS

        return [{"title": s, "link": None, "publisher": "Demo data (fictional)", "published": None}
                for s in SNIPPETS.splitlines()], True


def keyword_hits(title: str) -> list[str]:
    t = title.lower()
    return [k for k in ADVERSE_TERMS if re.search(rf"\b{re.escape(k)}", t)]


def highlight(title: str) -> str:
    """HTML-escaped title with adverse-media keywords wrapped in <mark class="hit">."""
    import html

    terms = "|".join(re.escape(k) for k in sorted(ADVERSE_TERMS, key=len, reverse=True))
    return re.sub(rf"(?i)\b((?:{terms})\w*)", r'<mark class="hit">\1</mark>', html.escape(title))

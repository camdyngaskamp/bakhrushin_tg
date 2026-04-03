from __future__ import annotations

import re
import datetime as dt
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

_RE_URL_DATE = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")


def _compile_many(patterns: Iterable[str] | None) -> list[re.Pattern]:
    return [re.compile(p) for p in (patterns or [])]


def _match_any(text: str, pats: list[re.Pattern]) -> bool:
    return True if not pats else any(p.search(text) for p in pats)


def _match_none(text: str, pats: list[re.Pattern]) -> bool:
    return True if not pats else not any(p.search(text) for p in pats)


def published_from_url(url: str) -> dt.datetime | None:
    m = _RE_URL_DATE.search(url)
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    return dt.datetime(y, mo, d, tzinfo=dt.timezone.utc)


def fetch_html_entries(url: str, parser_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Fetch a listing page and extract links as pseudo-feed entries.

    Returns list of dicts compatible with RSS fetcher output:
      {url, title, summary, published_at}

    parser_config options:
      - base_url: str (optional) - base for relative links (default = url)
      - list_selector: str (optional) - limit search to container
      - link_selector: str (optional, default 'a[href]')
      - include_regex: list[str] (optional) - keep links matching any pattern
      - exclude_regex: list[str] (optional) - drop links matching any pattern
      - same_domain: bool (optional, default True)
      - max_items: int (optional, default 50)
    """
    cfg = parser_config or {}
    base_url = (cfg.get("base_url") or url).strip()
    list_selector = (cfg.get("list_selector") or "").strip() or None
    link_selector = (cfg.get("link_selector") or "a[href]").strip()
    include_pats = _compile_many(cfg.get("include_regex"))
    exclude_pats = _compile_many(cfg.get("exclude_regex"))
    same_domain = bool(cfg.get("same_domain", True))
    max_items = int(cfg.get("max_items", 50))

    base_host = urlparse(base_url).netloc.lower()

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=HEADERS) as client:
        r = client.get(url)
        r.raise_for_status()
        html = r.text

    soup = BeautifulSoup(html, "lxml")
    scope = soup
    if list_selector:
        sel = soup.select_one(list_selector)
        if sel is not None:
            scope = sel

    anchors = scope.select(link_selector)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for a in anchors:
        href = (a.get("href") or "").strip()
        if not href:
            continue

        abs_url = urljoin(base_url, href).split("#", 1)[0]
        if abs_url in seen:
            continue

        host = urlparse(abs_url).netloc.lower()
        if same_domain and host and base_host and host != base_host:
            continue

        if not _match_any(abs_url, include_pats):
            continue
        if not _match_none(abs_url, exclude_pats):
            continue

        title = " ".join(a.get_text(" ", strip=True).split())
        if not title:
            parent = a.find_parent(["article", "div", "li"])
            if parent is not None:
                title = " ".join(parent.get_text(" ", strip=True).split())[:200]
        if not title:
            continue

        out.append(
            {
                "url": abs_url,
                "title": title[:300],
                "summary": None,
                "published_at": published_from_url(abs_url),
            }
        )
        seen.add(abs_url)

        if len(out) >= max_items:
            break

    return out

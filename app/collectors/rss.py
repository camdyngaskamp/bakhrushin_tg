from __future__ import annotations

import datetime as dt
import feedparser
import httpx

from app.utils.text import normalize_text

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_rss(url: str, timeout: float = 20.0) -> list[dict]:
    # feedparser can fetch itself, but we prefer httpx for timeouts and headers
    with httpx.Client(timeout=timeout, headers=HEADERS, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.text

    feed = feedparser.parse(data)
    out = []
    for e in feed.entries:
        link = getattr(e, "link", None)
        title = normalize_text(getattr(e, "title", "") or "")
        summary = getattr(e, "summary", "") or getattr(e, "description", "") or ""
        summary = normalize_text(summary)

        published_at = None
        for key in ("published_parsed", "updated_parsed"):
            val = getattr(e, key, None)
            if val:
                published_at = dt.datetime(*val[:6], tzinfo=dt.timezone.utc)
                break

        out.append({
            "url": link,
            "title": title,
            "summary": summary,
            "published_at": published_at,
            "raw": e,
        })
    return out

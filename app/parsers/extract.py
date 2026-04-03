from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
import trafilatura

from app.utils.text import normalize_text

HEADERS = {"User-Agent": "BakhrushinMuseumNewsBot/1.0 (+https://www.bakhrushinmuseum.ru/)"}

def extract_main_text(url: str, timeout: float = 20.0) -> tuple[str, str]:
    """Return (text, html). Uses trafilatura first, falls back to BeautifulSoup."""
    with httpx.Client(timeout=timeout, headers=HEADERS, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        html = r.text

    text = ""
    try:
        downloaded = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True)
        if downloaded:
            text = downloaded
    except Exception:
        text = ""

    if not text:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script","style","noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)

    return normalize_text(text), html

"""Opt-in browser transport; one context preserves cookies for a source run."""
from contextlib import contextmanager
import time

import httpx


class BrowserFetchError(RuntimeError):
    pass


class BrowserFetcher:
    def __init__(self, context, timeout_ms=45000):
        self.context = context
        self.timeout_ms = timeout_ms

    def fetch(self, url, *, wait_selector=None):
        page = self.context.new_page()
        deadline = time.monotonic() + self.timeout_ms / 1000
        def remaining():
            return max(1, int((deadline - time.monotonic()) * 1000))
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=remaining())
            # Challenge scripts may navigate after the initial 401 response.
            page.wait_for_function(
                """() => !document.querySelector('script[src*="/__qrator/"]')
                    && document.body && document.body.innerText.trim().length > 0""",
                timeout=remaining(),
            )
            if wait_selector:
                page.locator(wait_selector).first.wait_for(state="attached", timeout=remaining())
            # Read the current document status, rather than the initial challenge status.
            status = page.evaluate("() => performance.getEntriesByType('navigation')[0]?.responseStatus || 0")
            status = int(status or (response.status if response else 0))
            if status >= 400:
                raise httpx.HTTPStatusError(
                    f"Browser returned HTTP {status} for {url}",
                    request=httpx.Request("GET", url),
                    response=httpx.Response(status),
                )
            return page.content()
        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            raise BrowserFetchError(f"Browser could not load {url}: {exc}") from exc
        finally:
            page.close()


@contextmanager
def browser_fetcher(config=None):
    cfg = config or {}
    if cfg.get("fetch_mode", "http") != "browser":
        yield None
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserFetchError(
            "Browser mode requires Playwright: install requirements and run "
            "python -m playwright install --with-deps chromium"
        ) from exc
    timeout = int(cfg.get("browser_timeout_ms", 45000))
    if not 1000 <= timeout <= 120000:
        raise ValueError("browser_timeout_ms must be between 1000 and 120000")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel="chromium")
        try:
            context = browser.new_context(locale="ru-RU")
            try:
                yield BrowserFetcher(context, timeout)
            finally:
                context.close()
        finally:
            browser.close()

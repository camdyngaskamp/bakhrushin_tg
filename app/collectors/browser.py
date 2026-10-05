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
        document_status = None

        def record_document_response(response):
            nonlocal document_status
            if response.request.is_navigation_request() and response.frame == page.main_frame:
                document_status = response.status

        def diagnostics():
            # Do not log cookies, request headers or article contents.
            try:
                return {
                    "url": page.url,
                    "title": page.title(),
                    "http_status": document_status,
                    "qrator_script": page.locator('script[src*="/__qrator/"]').count() > 0,
                    "links": page.locator("a[href]").count(),
                    "wait_selector": wait_selector,
                }
            except Exception:
                return {"http_status": document_status, "wait_selector": wait_selector}

        def raise_http_error(details):
            if document_status is not None and document_status >= 400:
                raise httpx.HTTPStatusError(
                    f"Browser returned HTTP {document_status} for {url}; page={details}",
                    request=httpx.Request("GET", url),
                    response=httpx.Response(document_status),
                )

        page.on("response", record_document_response)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=remaining())
            # Challenge scripts may navigate after the initial 401 response.
            page.wait_for_function(
                """() => !document.querySelector('script[src*="/__qrator/"]')
                    && document.body && document.body.innerText.trim().length > 0""",
                timeout=remaining(),
            )
            raise_http_error(diagnostics())
            if wait_selector:
                page.locator(wait_selector).first.wait_for(state="attached", timeout=remaining())
            raise_http_error(diagnostics())
            return page.content()
        except httpx.HTTPStatusError:
            raise
        except Exception as exc:
            details = diagnostics()
            raise_http_error(details)
            raise BrowserFetchError(
                f"Browser could not load {url}; page={details}; reason={exc}"
            ) from exc
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

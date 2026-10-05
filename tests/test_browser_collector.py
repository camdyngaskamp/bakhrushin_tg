import unittest
from unittest.mock import MagicMock

import httpx

from app.collectors.browser import BrowserFetcher, BrowserFetchError, browser_fetcher
from app.collectors.html import fetch_html_entries
from app.parsers.extract import extract_main_text


class BrowserCollectorTests(unittest.TestCase):
    def test_listing_and_article_use_supplied_transport(self):
        fetcher = MagicMock()
        fetcher.fetch.side_effect = [
            '<a href="/news/story">Театральная премьера</a>',
            '<html><body><article><p>В театре состоялась премьера нового спектакля.</p></article></body></html>',
        ]
        entries = fetch_html_entries('https://example.org/news', {
            'include_regex': ['/news/'], 'browser_wait_selector': '.news-card',
        }, fetcher=fetcher)
        self.assertEqual(entries[0]['url'], 'https://example.org/news/story')
        text, html = extract_main_text(entries[0]['url'], fetcher=fetcher)
        self.assertIn('премьера', text)
        fetcher.fetch.assert_any_call('https://example.org/news', wait_selector='.news-card')
        fetcher.fetch.assert_any_call('https://example.org/news/story')

    def test_initial_challenge_status_does_not_override_final_success(self):
        context = MagicMock()
        page = context.new_page.return_value
        def navigate(*args, **kwargs):
            callback = page.on.call_args.args[1]
            for status in (401, 200):
                response = MagicMock(status=status, frame=page.main_frame)
                response.request.is_navigation_request.return_value = True
                callback(response)
        page.goto.side_effect = navigate
        page.content.return_value = '<html>Новости</html>'
        self.assertEqual(BrowserFetcher(context).fetch('https://example.org'), '<html>Новости</html>')
        page.close.assert_called_once()

    def test_final_http_error_is_not_success(self):
        context = MagicMock()
        page = context.new_page.return_value
        def navigate(*args, **kwargs):
            response = MagicMock(status=403, frame=page.main_frame)
            response.request.is_navigation_request.return_value = True
            page.on.call_args.args[1](response)
        page.goto.side_effect = navigate
        with self.assertRaises(httpx.HTTPStatusError):
            BrowserFetcher(context).fetch('https://example.org')
        page.locator.return_value.first.wait_for.assert_not_called()
        page.close.assert_called_once()

    def test_unresolved_challenge_closes_page(self):
        context = MagicMock()
        page = context.new_page.return_value
        page.wait_for_function.side_effect = RuntimeError('timeout')
        with self.assertRaisesRegex(BrowserFetchError, 'http_status'):
            BrowserFetcher(context).fetch('https://example.org')
        page.content.assert_not_called()
        page.close.assert_called_once()

    def test_missing_selector_reports_page_details(self):
        context = MagicMock()
        page = context.new_page.return_value
        page.url = 'https://example.org/news'
        page.title.return_value = 'Access denied'
        page.locator.return_value.count.return_value = 0
        page.locator.return_value.first.wait_for.side_effect = RuntimeError('selector timeout')
        with self.assertRaisesRegex(BrowserFetchError, 'Access denied'):
            BrowserFetcher(context).fetch('https://example.org/news', wait_selector='.news')
        page.close.assert_called_once()

    def test_subresource_error_does_not_replace_document_status(self):
        context = MagicMock()
        page = context.new_page.return_value
        def navigate(*args, **kwargs):
            callback = page.on.call_args.args[1]
            for status, navigation in ((200, True), (403, False)):
                response = MagicMock(status=status, frame=page.main_frame)
                response.request.is_navigation_request.return_value = navigation
                callback(response)
        page.goto.side_effect = navigate
        page.content.return_value = '<html>News</html>'
        self.assertEqual(BrowserFetcher(context).fetch('https://example.org'), '<html>News</html>')

    def test_http_mode_does_not_require_playwright(self):
        with browser_fetcher({}) as fetcher:
            self.assertIsNone(fetcher)


if __name__ == '__main__':
    unittest.main()

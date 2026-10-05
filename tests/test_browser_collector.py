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
        page.goto.return_value.status = 401
        page.evaluate.return_value = 200
        page.content.return_value = '<html>Новости</html>'
        self.assertEqual(BrowserFetcher(context).fetch('https://example.org'), '<html>Новости</html>')
        page.close.assert_called_once()

    def test_final_http_error_is_not_success(self):
        context = MagicMock()
        page = context.new_page.return_value
        page.evaluate.return_value = 403
        with self.assertRaises(httpx.HTTPStatusError):
            BrowserFetcher(context).fetch('https://example.org')
        page.close.assert_called_once()

    def test_unresolved_challenge_closes_page(self):
        context = MagicMock()
        page = context.new_page.return_value
        page.wait_for_function.side_effect = RuntimeError('timeout')
        with self.assertRaises(BrowserFetchError):
            BrowserFetcher(context).fetch('https://example.org')
        page.content.assert_not_called()
        page.close.assert_called_once()

    def test_http_mode_does_not_require_playwright(self):
        with browser_fetcher({}) as fetcher:
            self.assertIsNone(fetcher)


if __name__ == '__main__':
    unittest.main()

import unittest
from app.collectors.cookie_import import cookies_from_header


class CookieImportTests(unittest.TestCase):
    def test_values_preserve_equals_and_target_host_scope(self):
        cookies = cookies_from_header('qrator_jsr=abc|def==; other=', 'https://bolshoi.ru/news')
        self.assertEqual(cookies, [
            {'name': 'qrator_jsr', 'value': 'abc|def==', 'url': 'https://bolshoi.ru/'},
            {'name': 'other', 'value': '', 'url': 'https://bolshoi.ru/'},
        ])

    def test_optional_header_name(self):
        self.assertEqual(cookies_from_header('Cookie: session=value\n', 'https://example.org')[0]['name'], 'session')

    def test_bad_inputs_do_not_expose_cookie_values(self):
        for header in ('', 'secret-token', 'session=SECRET\nother=SECRET', 'session=SECRET; session=SECRET', 'curl https://example.org'):
            with self.assertRaises(ValueError) as caught:
                cookies_from_header(header, 'https://example.org')
            self.assertNotIn('SECRET', str(caught.exception))

    def test_invalid_destination(self):
        for url in ('file:///tmp/file', 'https://user:pass@example.org', 'no-host'):
            with self.assertRaises(ValueError):
                cookies_from_header('session=value', url)

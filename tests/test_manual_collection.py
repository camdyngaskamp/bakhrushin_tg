from contextlib import redirect_stderr
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

import httpx
from app.collectors.browser import BrowserFetchError
from app.scripts.collect_bolshoi import collect_with_status


class ManualCollectionTests(unittest.TestCase):
    def test_denial_rolls_back_before_recording_error(self):
        for status in (401, 403):
            db = MagicMock()
            source = SimpleNamespace(fail_streak=1, enabled=True)
            error = httpx.HTTPStatusError('HTTP 401; title=HTTP 403', request=httpx.Request('GET', 'https://bolshoi.ru/news'), response=httpx.Response(status))
            collector = MagicMock(side_effect=error)
            events = []
            db.rollback.side_effect = lambda: events.append('rollback')
            db.commit.side_effect = lambda: events.append(('commit', source.last_status_code))
            output = StringIO()
            with redirect_stderr(output):
                result = collect_with_status(db, source, collector)
            self.assertEqual(result, 2)
            self.assertEqual(events, ['rollback', ('commit', status)])
            self.assertEqual(source.fail_streak, 2)
            self.assertIsNotNone(source.last_checked_at)
            self.assertIn('title=HTTP 403', source.last_error)
            self.assertTrue(source.enabled)
            self.assertIn('Получите свежие cookies', output.getvalue())
            self.assertNotIn('Traceback', output.getvalue())

    def test_success_resets_health(self):
        source = SimpleNamespace(fail_streak=3, last_error='old error')
        db = MagicMock()
        self.assertEqual(collect_with_status(db, source, MagicMock()), 0)
        self.assertEqual(source.last_status_code, 200)
        self.assertEqual(source.fail_streak, 0)
        self.assertIsNone(source.last_error)
        db.rollback.assert_not_called()
        db.commit.assert_called_once()

    def test_browser_timeout_is_not_reported_as_denial(self):
        source = SimpleNamespace(fail_streak=3)
        db = MagicMock()
        with redirect_stderr(StringIO()) as output:
            result = collect_with_status(db, source, MagicMock(side_effect=BrowserFetchError('timeout')))
        self.assertEqual(result, 3)
        self.assertIsNone(source.last_status_code)
        self.assertEqual(source.fail_streak, 0)
        self.assertNotIn('Получите свежие cookies', output.getvalue())
        db.rollback.assert_called_once()

    def test_unexpected_bug_is_not_hidden_as_cookie_problem(self):
        with self.assertRaises(TypeError):
            collect_with_status(MagicMock(), SimpleNamespace(), MagicMock(side_effect=TypeError('bug')))

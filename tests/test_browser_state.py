import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.collectors.browser_state import BrowserState, browser_state


class BrowserStateTests(unittest.TestCase):
    def test_state_roundtrip_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('app.collectors.browser_state.STATE_DIR', Path(directory)):
                with browser_state('bolshoi') as state:
                    self.assertIsNone(state.load())
                    context = MagicMock()
                    context.storage_state.return_value = {'cookies': [{'name': 'test', 'value': 'value'}], 'origins': []}
                    state.save(context)
                    self.assertEqual(state.load(), context.storage_state.return_value)
                    self.assertEqual(state.path.stat().st_mode & 0o777, 0o600)
                with browser_state('bolshoi') as reopened:
                    self.assertEqual(reopened.load()['cookies'][0]['name'], 'test')

    def test_failed_save_preserves_previous_state(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('app.collectors.browser_state.STATE_DIR', Path(directory)):
                with browser_state('bolshoi') as state:
                    old = {'cookies': [], 'origins': []}
                    state.path.write_text(json.dumps(old))
                    context = MagicMock()
                    context.storage_state.side_effect = RuntimeError('failed')
                    with self.assertRaises(RuntimeError):
                        state.save(context)
                    self.assertEqual(state.load(), old)

    def test_invalid_name_cannot_escape_directory(self):
        for name in ('../cookies', '/tmp/cookies', '', 'name.json'):
            with self.assertRaises(ValueError):
                BrowserState(name)

    def test_bad_json_reports_no_cookie_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('app.collectors.browser_state.STATE_DIR', Path(directory)):
                with browser_state('bolshoi') as state:
                    state.path.write_text('secret-cookie-invalid-json')
                    with self.assertRaises(ValueError) as caught:
                        state.load()
                    self.assertNotIn('secret-cookie', str(caught.exception))

    def test_state_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('app.collectors.browser_state.STATE_DIR', Path(directory)):
                with browser_state('bolshoi') as state:
                    state.path.symlink_to(Path(directory) / 'other.json')
                    with self.assertRaises(ValueError):
                        state.load()

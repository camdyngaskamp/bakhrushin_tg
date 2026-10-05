"""Private, atomic Playwright state storage shared by API and workers (Linux)."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import time

STATE_DIR = Path(__file__).resolve().parents[2] / '.browser-state'


class BrowserState:
    def __init__(self, name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', name):
            raise ValueError('browser_state_name must contain 1–64 letters, digits, underscores or hyphens')
        self.name = name
        self.path = STATE_DIR / f'{name}.json'

    def load(self):
        if self.path.is_symlink():
            raise ValueError('Browser state must not be a symbolic link')
        if not self.path.exists():
            return None
        try:
            state = json.loads(self.path.read_text())
            if not isinstance(state, dict) or not isinstance(state.get('cookies'), list) or not isinstance(state.get('origins'), list):
                raise ValueError('Invalid state structure')
            return state
        except (ValueError, OSError) as exc:
            # Do not print the contents of state files or cookies.
            raise ValueError(f'Cannot read browser session {self.name}; re-export its Playwright storage state') from exc

    def save(self, context):
        state = context.storage_state()
        fd, temporary = tempfile.mkstemp(prefix=f'.{self.name}-', dir=STATE_DIR)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(state, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


@contextmanager
def browser_state(name):
    if not name:
        yield None
        return
    state = BrowserState(name)
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if STATE_DIR.is_symlink():
        raise ValueError('Browser state directory must not be a symbolic link')
    # Serialize a complete source run so Test and Celery do not overwrite cookies.
    fd = os.open(STATE_DIR / f'{name}.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        deadline = time.monotonic() + 5
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f'Browser session {name} is busy; retry after the current source run')
                time.sleep(0.1)
        yield state
    finally:
        os.close(fd)

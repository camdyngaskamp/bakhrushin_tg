"""Parse a copied request Cookie header without evaluating or logging its contents."""
import re
from urllib.parse import urlsplit


def cookies_from_header(header: str, url: str) -> list[dict]:
    target = urlsplit(url)
    if target.scheme not in ('http', 'https') or not target.hostname or target.username or target.password:
        raise ValueError('Cookie import requires an HTTP(S) URL without credentials')
    header = header.strip()
    if header.lower().startswith('cookie:'):
        header = header.split(':', 1)[1].strip()
    if not header or len(header) > 65536 or '\n' in header or '\r' in header:
        raise ValueError('Provide a single nonempty Cookie request header, not a cURL command or response headers')
    origin = f'{target.scheme}://{target.netloc}/'
    cookies = []
    names = set()
    for part in header.split(';'):
        name, separator, value = part.strip().partition('=')
        if not separator or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
            raise ValueError('Invalid Cookie header format')
        if name in names:
            raise ValueError('Duplicate cookie names: use a full cookie export to preserve different paths')
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('Invalid control character in Cookie header')
        names.add(name)
        # Request headers omit original path, expiry and flags. Scope the test to
        # the exact requested host, root path, and retain cookies as session-only.
        cookies.append({'name': name, 'value': value, 'url': origin})
    return cookies

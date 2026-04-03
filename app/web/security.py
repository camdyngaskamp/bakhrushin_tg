from __future__ import annotations

from urllib.parse import urlencode


def sanitize_next_path(value: str | None) -> str:
    if not value:
        return "/"
    value = value.strip()
    if not value:
        return "/"
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


def login_url(error: str | None = None, next_path: str | None = None) -> str:
    params: dict[str, str] = {}
    if error:
        params["error"] = error
    if next_path and next_path != "/":
        params["next"] = next_path
    if not params:
        return "/login"
    return f"/login?{urlencode(params)}"


__all__ = ["sanitize_next_path", "login_url"]

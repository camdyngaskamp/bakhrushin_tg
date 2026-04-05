#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

# Load .env before anything else so os.getenv() picks up project settings.
# dotenv_values() is not used here — we want variables to land in os.environ
# so that downstream imports (app.config, app.ai.*) also see them.
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on environment being pre-set

from openai import OpenAI


@dataclass
class CheckResult:
    name: str
    ok: bool
    duration_sec: float
    details: str
    extra: dict[str, Any] | None = None


def _now() -> float:
    return time.perf_counter()


def run_check(name: str, func):
    started = _now()
    try:
        result = func()
        if isinstance(result, tuple):
            ok, details, extra = result
        else:
            ok, details, extra = True, str(result), None
    except Exception as exc:
        ok = False
        details = f"{type(exc).__name__}: {exc}"
        extra = {"traceback": traceback.format_exc(limit=5)}
    return CheckResult(
        name=name,
        ok=ok,
        duration_sec=round(_now() - started, 3),
        details=details,
        extra=extra,
    )


def get_env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def check_env():
    required = ["AI_API_KEY"]
    optional = ["AI_BASE_URL", "AI_MODEL", "AI_PROVIDER", "TG_PUBLISH_LANGUAGE"]

    missing = [k for k in required if not get_env(k)]
    snapshot = {k: ("***set***" if get_env(k) else None) for k in required}
    snapshot.update({k: get_env(k) for k in optional})

    if missing:
        return False, f"Missing required env vars: {', '.join(missing)}", snapshot
    return True, "Environment looks OK", snapshot


def make_client(timeout: float):
    return OpenAI(
        api_key=os.environ["AI_API_KEY"],
        base_url=os.getenv("AI_BASE_URL", "https://openrouter.ai/api/v1"),
        timeout=timeout,
    )


def check_openai_direct(timeout: float):
    model = os.getenv("AI_MODEL", "openai/gpt-4o-mini")
    client = make_client(timeout=timeout)

    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": "You are a diagnostic assistant."},
            {"role": "user", "content": "Reply with exactly: AI_OK"},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()

    if text != "AI_OK":
        return False, f"Unexpected direct response: {text!r}", {"model": model}

    usage = None
    if getattr(resp, "usage", None):
        try:
            usage = resp.usage.model_dump()
        except Exception:
            usage = str(resp.usage)

    return True, "Direct AI call succeeded", {
        "model": model,
        "finish_reason": resp.choices[0].finish_reason,
        "usage": usage,
    }


def check_project_summarizer():
    mod = importlib.import_module("app.ai.summarize")
    if not hasattr(mod, "generate_post"):
        return False, "app.ai.summarize.generate_post not found", None

    text = (
        "В Бахрушинском музее открылась новая выставка, посвященная истории театрального искусства. "
        "В экспозиции представлены архивные документы, эскизы костюмов и редкие фотографии. "
        "Выставка будет открыта до конца месяца."
    )

    result = mod.generate_post(
        title="Новая выставка в Бахрушинском музее",
        text=text,
        url="https://example.org/healthcheck-news",
    )

    out = (result or "").strip()
    if not out:
        return False, "Project summarizer returned empty output", None
    if len(out) < 40:
        return False, f"Project summarizer output too short: {out!r}", {"output": out}

    return True, "Project summarizer succeeded", {"output_preview": out[:300]}


def check_translation(skip: bool):
    if skip:
        return True, "Translation check skipped by flag", None

    channel_lang = (os.getenv("TG_PUBLISH_LANGUAGE", "ru") or "ru").lower()

    mod = importlib.import_module("app.ai.translate")
    supported = getattr(mod, "SUPPORTED_TRANSLATION_LANGS", ("th", "en", "es"))

    if channel_lang not in supported:
        return True, f"Translation check skipped because TG_PUBLISH_LANGUAGE={channel_lang!r} is not a translated language", None

    fn = getattr(mod, "translate_ru", None)
    if fn is None:
        for name in ("translate_text", "translate"):
            if hasattr(mod, name):
                fn = getattr(mod, name)
                break

    if fn is None:
        return False, "No translation function found in app.ai.translate", None

    source_text = "В Бахрушинском музее открылась новая выставка о театральном искусстве."
    translated = fn(source_text, target_lang=channel_lang)

    out = (translated or "").strip()
    if not out:
        return False, "Translation function returned empty output", None

    # Confirm output was actually translated away from Russian (Cyrillic = untranslated)
    has_cyrillic = any("\u0400" <= ch <= "\u04FF" for ch in out)
    if has_cyrillic:
        return False, f"Output still contains Cyrillic — translation may have failed: {out!r}", {"output": out[:300]}

    if channel_lang == "th":
        has_thai = any("\u0E00" <= ch <= "\u0E7F" for ch in out)
        if not has_thai:
            return False, f"Output does not look like Thai text: {out!r}", {"output": out[:300]}
    else:
        # Latin-script languages (en, es, …)
        has_latin = any(("A" <= ch <= "Z") or ("a" <= ch <= "z") for ch in out)
        if not has_latin:
            return False, f"Output does not look like {channel_lang.upper()} text (no Latin chars): {out!r}", {"output": out[:300]}

    lang_name = (getattr(mod, "LANG_PROMPTS", {}).get(channel_lang) or {}).get("name", channel_lang.upper())
    return True, f"{lang_name} translation succeeded", {"output_preview": out[:300]}


def check_db_connectivity():
    from sqlalchemy import text
    from app.db.session import engine

    with engine.connect() as conn:
        value = conn.execute(text("select 1")).scalar()
    return (value == 1), f"DB connectivity returned {value}", None


def build_report(args):
    return [
        run_check("env", check_env),
        run_check("db_connectivity", check_db_connectivity),
        run_check("openai_direct", lambda: check_openai_direct(args.timeout)),
        run_check("project_summarizer", check_project_summarizer),
        run_check("translation", lambda: check_translation(args.skip_translation)),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--skip-translation", action="store_true", help="Skip translation-specific checks")
    parser.add_argument("--timeout", type=float, default=45.0, help="API timeout in seconds")
    args = parser.parse_args()

    results = build_report(args)
    ok = all(r.ok for r in results)

    if args.json:
        print(json.dumps({"ok": ok, "results": [asdict(r) for r in results]}, ensure_ascii=False, indent=2))
    else:
        print("AI HEALTHCHECK")
        print("=" * 60)
        for r in results:
            status = "OK" if r.ok else "FAIL"
            print(f"[{status}] {r.name} ({r.duration_sec:.3f}s)")
            print(f"  {r.details}")
            if r.extra:
                for k, v in r.extra.items():
                    if v is None:
                        continue
                    if isinstance(v, str) and len(v) > 500:
                        v = v[:500] + "..."
                    print(f"  {k}: {v}")
            print("-" * 60)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

from __future__ import annotations

from app.ai.client import get_ai_client
from app.config import settings

THAI_TONE = {
    "formal": "สุภาพ เป็นทางการ เหมาะกับพิพิธภัณฑ์และข่าววัฒนธรรม",
    "neutral": "เป็นกลาง อ่านง่าย เหมาะกับข่าวสาร",
    "social": "เป็นกันเอง แต่ยังคงสุภาพ เหมาะกับโซเชียลมีเดีย",
}

LANG_PROMPTS = {
    "th": {
        "name": "Thai",
        "system": "You are a professional Thai translator for a cultural museum Telegram channel.",
        "tone_map": THAI_TONE,
        "default_tone": THAI_TONE["neutral"],
    },
    "en": {
        "name": "English",
        "system": "You translate Russian cultural news into polished English for Telegram posts.",
        "default_tone": "Warm, concise museum editorial voice suitable for Telegram.",
    },
    "es": {
        "name": "Spanish",
        "system": "You translate Russian cultural news into natural Latin American Spanish for Telegram posts.",
        "default_tone": "Amable e informativo tono editorial de museo, sin jerga innecesaria.",
    },
    "it": {
        "name": "Italian",
        "system": "You translate Russian cultural news into natural Italian for Telegram posts.",
        "default_tone": "Tono editoriale museale, chiaro, sobrio e coinvolgente.",
    },
}

SUPPORTED_TRANSLATION_LANGS = tuple(sorted(LANG_PROMPTS.keys()))


def translate_ru(text_ru: str, *, target_lang: str, style: str = "neutral") -> str:
    """Translate Russian text to a supported target language for Telegram publication."""

    text_ru = (text_ru or "").strip()
    if not text_ru:
        return ""

    lang = (target_lang or "").lower()
    if lang not in LANG_PROMPTS:
        raise ValueError(f"Unsupported translation language: {target_lang}")

    meta = LANG_PROMPTS[lang]
    tone_map = meta.get("tone_map")
    tone_line = None
    if tone_map:
        tone_line = tone_map.get(style, tone_map["neutral"])
    else:
        tone_line = meta.get("default_tone")

    rules = [
        f"Translate the following Russian text into {meta['name']} for a Telegram post.",
        "Rules:",
        "- Preserve line breaks, URLs, HTML entities, and hashtags exactly as in the source.",
        "- Keep proper nouns (people, theatres, institutions) accurate; do not invent facts.",
        "- Maintain dates, numbers, and measurements without conversion unless required by grammar.",
    ]
    if tone_line:
        rules.append(f"- Tone: {tone_line}")
    rules.append("- Output ONLY the translated text, without explanations or transliteration duplicates.")

    user_prompt = "\n".join(rules) + f"\n\nText:\n{text_ru}"

    client = get_ai_client()
    resp = client.chat.completions.create(
        model=settings.tg_translation_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": meta["system"]},
            {"role": "user", "content": user_prompt},
        ],
    )
    out = resp.choices[0].message.content or ""
    return out.strip()


def translate_ru_to_th(text_ru: str, *, style: str = "neutral") -> str:
    """Backward-compatible helper for Thai translation."""

    return translate_ru(text_ru, target_lang="th", style=style)

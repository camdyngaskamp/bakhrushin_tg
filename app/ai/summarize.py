from __future__ import annotations
from app.ai.client import get_ai_client
from app.ai.prompts import SYSTEM_PROMPT_V1, user_prompt
from app.config import settings

def generate_post(title: str, text: str, url: str) -> str:
    client = get_ai_client()
    resp = client.chat.completions.create(
        model=settings.ai_model,
        temperature=settings.ai_temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_V1},
            {"role": "user", "content": user_prompt(title=title or "", text=text or "", url=url)},
        ],
    )
    content = (resp.choices[0].message.content or "").strip()
    return content

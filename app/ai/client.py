from __future__ import annotations
from openai import OpenAI
from app.config import settings

def get_ai_client() -> OpenAI:
    return OpenAI(
        api_key=settings.polza_api_key,
        base_url=settings.polza_base_url,
    )

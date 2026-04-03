from __future__ import annotations
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import settings

def _build_session() -> AiohttpSession:
    proxy = settings.telegram_proxy
    if not proxy:
        return AiohttpSession()
    try:
        return AiohttpSession(proxy=proxy)
    except RuntimeError as exc:
        raise RuntimeError("aiohttp_socks is required to use telegram_proxy") from exc


def get_bot() -> Bot:
    session = _build_session()
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=None),
        session=session,
    )

async def send_to_channel(text: str) -> str:
    bot = get_bot()
    try:
        msg = await bot.send_message(chat_id=settings.telegram_channel, text=text, disable_web_page_preview=False)
        return str(msg.message_id)
    finally:
        # aiogram uses aiohttp under the hood; close session to avoid "Unclosed client session" warnings.
        await bot.session.close()

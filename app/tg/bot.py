from __future__ import annotations
import asyncio
import datetime as dt

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from app.config import settings
from app.db.session import SessionLocal
from app.db.models import Post, ModerationStatus

dp = Dispatcher()

def is_admin(user_id: int) -> bool:
    admins = settings.telegram_admin_id_set
    return (not admins) or (user_id in admins)

def kb_for_post(post_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Approve", callback_data=f"approve:{post_id}")
    kb.button(text="⏰ Schedule +1h", callback_data=f"schedule1h:{post_id}")
    kb.button(text="❌ Reject", callback_data=f"reject:{post_id}")
    kb.button(text="📝 Edit (reply text)", callback_data=f"edit:{post_id}")
    kb.adjust(2,2)
    return kb.as_markup()

@dp.message(Command("start"))
async def start(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("Access denied.")
    await m.answer("Bakhrushin moderation bot.
Commands:
/queue — show pending
/help")

@dp.message(Command("help"))
async def help_cmd(m: Message):
    await m.answer("Commands:
/queue — show pending posts
You can also reply with new text after pressing Edit.")

@dp.message(Command("queue"))
async def queue(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("Access denied.")
    with SessionLocal() as db:
        posts = db.scalars(
            select(Post).where(Post.moderation_status == ModerationStatus.pending).order_by(Post.created_at.asc()).limit(10)
        ).all()
        if not posts:
            return await m.answer("Queue is empty.")
        for p in posts:
            src = p.item.url if p.item else ""
            text = (p.tg_text or "")[:3500]
            await m.answer(f"Post #{p.id}\n{src}\n\n{text}", reply_markup=kb_for_post(p.id))

@dp.callback_query(F.data.startswith("approve:"))
async def approve_cb(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        return await q.answer("Denied", show_alert=True)
    post_id = int(q.data.split(":")[1])
    with SessionLocal() as db:
        p = db.get(Post, post_id)
        if not p:
            return await q.answer("Not found", show_alert=True)
        p.moderation_status = ModerationStatus.approved
        db.commit()
    await q.answer("Approved")

@dp.callback_query(F.data.startswith("reject:"))
async def reject_cb(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        return await q.answer("Denied", show_alert=True)
    post_id = int(q.data.split(":")[1])
    with SessionLocal() as db:
        p = db.get(Post, post_id)
        if not p:
            return await q.answer("Not found", show_alert=True)
        p.moderation_status = ModerationStatus.rejected
        db.commit()
    await q.answer("Rejected")

@dp.callback_query(F.data.startswith("schedule1h:"))
async def schedule1h_cb(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        return await q.answer("Denied", show_alert=True)
    post_id = int(q.data.split(":")[1])
    when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
    with SessionLocal() as db:
        p = db.get(Post, post_id)
        if not p:
            return await q.answer("Not found", show_alert=True)
        p.scheduled_at = when
        p.moderation_status = ModerationStatus.scheduled
        db.commit()
    await q.answer("Scheduled +1h (UTC)")

@dp.callback_query(F.data.startswith("edit:"))
async def edit_cb(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        return await q.answer("Denied", show_alert=True)
    post_id = int(q.data.split(":")[1])
    await q.message.answer(f"Send new text as a reply to this message with prefix: EDIT {post_id}\nExample:\nEDIT {post_id}\n<new text>")
    await q.answer()

@dp.message(F.text.startswith("EDIT "))
async def edit_text(m: Message):
    if not is_admin(m.from_user.id):
        return await m.answer("Access denied.")
    lines = (m.text or "").splitlines()
    head = lines[0].strip()
    parts = head.split()
    if len(parts) < 2:
        return await m.answer("Bad format. Use: EDIT <post_id> on first line.")
    try:
        post_id = int(parts[1])
    except ValueError:
        return await m.answer("Bad post_id.")
    new_text = "\n".join(lines[1:]).strip()
    if not new_text:
        return await m.answer("Empty text.")
    with SessionLocal() as db:
        p = db.get(Post, post_id)
        if not p:
            return await m.answer("Not found.")
        p.tg_text = new_text
        db.commit()
    await m.answer(f"Updated post #{post_id}.", reply_markup=kb_for_post(post_id))

async def main():
    bot = Bot(token=settings.telegram_bot_token)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

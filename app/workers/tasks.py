from __future__ import annotations

import datetime as dt
import logging
import httpx

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Source, SourceType, Item, ItemStatus, Post, ModerationStatus
from app.collectors.rss import fetch_rss
from app.collectors.html import fetch_html_entries
from app.parsers.extract import extract_main_text
from app.utils.text import text_hash, normalize_text
from app.ai.summarize import generate_post
from app.ai.translate import translate_ru, SUPPORTED_TRANSLATION_LANGS
from app.tg.sender import send_to_channel
from rapidfuzz.fuzz import ratio
from app.config import settings

logger = logging.getLogger(__name__)

THEATRE_KEYWORDS = [
    "театр","премьера","спектакль","режисс","актер","актриса","сцена","фестиваль","драма","опера","балет",
    "постановк","гастрол","репертуар","труппа","мюзикл","капустник","читк","перформанс","хореограф",
]

def is_theatre_related(text: str) -> bool:
    t = (text or "").lower()
    if not t:
        return False
    hits = sum(1 for k in THEATRE_KEYWORDS if k in t)
    return hits >= 2  # tweak

def similar_enough(a: str, b: str) -> bool:
    # Fast fuzzy similarity threshold
    if not a or not b:
        return False
    return ratio(a[:1500], b[:1500]) >= 93


def _set_translated_text(post: Post, target_lang: str, translated: str) -> None:
    if target_lang == "th":
        post.tg_text_th = translated
    elif target_lang == "en":
        post.tg_text_en = translated
    elif target_lang == "es":
        post.tg_text_es = translated
    elif target_lang == "it":
        post.tg_text_it = translated


def _auto_translate_post_if_needed(post: Post) -> tuple[bool, str | None]:
    lang = (settings.tg_publish_language or "").strip().lower()
    if lang == "ru":
        return True, None
    if lang not in SUPPORTED_TRANSLATION_LANGS:
        return False, f"Unsupported TG_PUBLISH_LANGUAGE for auto-translation: {settings.tg_publish_language}"
    if not settings.auto_translate_after_ai_selection:
        return False, "AUTO_TRANSLATE_AFTER_AI_SELECTION=false and non-RU publish language requires translation"

    source_text = (post.tg_text or "").strip()
    if not source_text:
        return False, "Cannot auto-translate empty tg_text"

    translated = translate_ru(source_text, target_lang=lang, style=settings.tg_translation_style)
    if not translated.strip():
        return False, f"Empty translation output for language: {lang}"

    _set_translated_text(post, lang, translated.strip())
    return True, None


def _cutoff_utc(days: int | None, absolute: dt.datetime | None) -> dt.datetime | None:
    """Return cutoff datetime in UTC.

    Priority:
      1) sliding window in days
      2) absolute datetime/date
    """
    if days is not None:
        return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=int(days))
    if absolute is None:
        return None
    if absolute.tzinfo is None:
        return absolute.replace(tzinfo=dt.timezone.utc)
    return absolute.astimezone(dt.timezone.utc)


@shared_task(name="app.workers.tasks.collect_all_sources")
def collect_all_sources():
    now = dt.datetime.now(dt.timezone.utc)
    with SessionLocal() as db:
        sources = db.scalars(select(Source).where(Source.enabled == True)).all()  # noqa: E712

        for src in sources:
            try:
                if src.type == SourceType.rss:
                    _collect_rss_source(db, src)
                else:
                    _collect_html_source(db, src)

                src.last_status_code = 200
                src.last_error = None
                src.last_checked_at = now
                src.fail_streak = 0
                db.commit()

            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response else None
                src.last_status_code = status
                src.last_error = f"{status} {e}"
                src.last_checked_at = now

                # опционально: авто-выключение на 401/403
                if status in (401, 403):
                    src.fail_streak = (src.fail_streak or 0) + 1

                    if settings.auto_disable_on_401_403 and src.fail_streak >= settings.auto_disable_threshold:
                        src.enabled = False
                    logger.warning(
                            "[auto-disable] source_id=%s url=%s disabled after %s consecutive %s",
                            src.id, src.url, src.fail_streak, status
                        )
                else:
                    # другая ошибка/код — считаем как сброс streak (или можно вести отдельно)
                    src.fail_streak = 0

                db.commit()
                logger.warning("[collect] source_id=%s url=%s failed: %s", src.id, src.url, src.last_error)
            
            except Exception as e:
                src.last_status_code = None
                src.last_error = str(e)
                src.last_checked_at = now
                db.commit()
                logger.exception("[collect] source_id=%s url=%s unexpected error", src.id, src.url)


def _collect_rss_source(db: Session, src: Source):
    cutoff = _cutoff_utc(settings.news_not_before_days, settings.news_not_before)
    skipped_cutoff = 0
    added = 0
    entries = fetch_rss(src.url)
    for e in entries:
        url = e.get("url")
        if not url:
            continue
        # Skip if exists
        if db.scalar(select(Item.id).where(Item.url == url)) is not None:
            continue

        title = e.get("title") or ""
        summary = e.get("summary") or ""
        published_at = e.get("published_at")

        # Skip old items (if date is known)
        if cutoff and published_at:
            try:
                pub = published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=dt.timezone.utc)
                else:
                    pub = pub.astimezone(dt.timezone.utc)
                if pub < cutoff:
                    skipped_cutoff += 1
                    logger.info(
                        "[cutoff] skipped by NEWS_NOT_BEFORE source_id=%s url=%s published_at=%s cutoff=%s",
                        src.id,
                        url,
                        pub.isoformat(),
                        cutoff.isoformat(),
                    )
                    continue
            except Exception:
                # If date parsing is weird, don't block collection.
                pass

        # Try to extract main text for better AI + filters
        raw_text = ""
        raw_html = ""
        try:
            raw_text, raw_html = extract_main_text(url)
        except Exception:
            raw_text = normalize_text(summary) or normalize_text(title)
            raw_html = None

        combined = normalize_text(" ".join([title, summary, raw_text]))
        if len(combined) < 400:
            # too little info; keep but mark rejected
            status = ItemStatus.rejected
        else:
            status = ItemStatus.new

        item = Item(
            source_id=src.id,
            url=url,
            title=title,
            published_at=published_at,
            raw_text=raw_text,
            raw_html=raw_html,
            hash_text=text_hash(raw_text or summary or title),
            status=status,
        )

        # Dedup by hash similarity against recent items
        if status != ItemStatus.rejected:
            recent = db.scalars(
                select(Item).where(Item.hash_text == item.hash_text).order_by(Item.created_at.desc()).limit(5)
            ).all()
            if recent:
                status = ItemStatus.rejected
                item.status = status

        db.add(item)
        added += 1

    logger.info(
        "[collect] source_id=%s type=rss added=%s skipped_cutoff=%s cutoff=%s",
        src.id,
        added,
        skipped_cutoff,
        cutoff.isoformat() if cutoff else None,
    )



def _collect_html_source(db: Session, src: Source):
    cutoff = _cutoff_utc(settings.news_not_before_days, settings.news_not_before)
    skipped_cutoff = 0
    added = 0
    entries = fetch_html_entries(url=src.url, parser_config=src.parser_config)
    for e in entries:
        url = e.get("url")
        if not url:
            continue
        if db.scalar(select(Item.id).where(Item.url == url)) is not None:
            continue

        title = e.get("title") or ""
        summary = e.get("summary") or ""
        published_at = e.get("published_at")

        # Skip old items (if date is known)
        if cutoff and published_at:
            try:
                pub = published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=dt.timezone.utc)
                else:
                    pub = pub.astimezone(dt.timezone.utc)
                if pub < cutoff:
                    skipped_cutoff += 1
                    logger.info(
                        "[cutoff] skipped by NEWS_NOT_BEFORE source_id=%s url=%s published_at=%s cutoff=%s",
                        src.id,
                        url,
                        pub.isoformat(),
                        cutoff.isoformat(),
                    )
                    continue
            except Exception:
                pass

        raw_text = ""
        raw_html = ""
        try:
            raw_text, raw_html = extract_main_text(url)
        except Exception:
            raw_text = normalize_text(summary) or normalize_text(title)
            raw_html = None

        combined = normalize_text(" ".join([title, summary, raw_text]))
        status = ItemStatus.new if len(combined) >= 400 else ItemStatus.rejected

        item = Item(
            source_id=src.id,
            url=url,
            title=title,
            published_at=published_at,
            raw_text=raw_text,
            raw_html=raw_html,
            hash_text=text_hash(raw_text or summary or title),
            status=status,
        )

        if status != ItemStatus.rejected:
            recent = db.scalars(
                select(Item).where(Item.hash_text == item.hash_text).order_by(Item.created_at.desc()).limit(5)
            ).all()
            if recent:
                item.status = ItemStatus.rejected

        db.add(item)
        added += 1

    logger.info(
        "[collect] source_id=%s type=html added=%s skipped_cutoff=%s cutoff=%s",
        src.id,
        added,
        skipped_cutoff,
        cutoff.isoformat() if cutoff else None,
    )

@shared_task(name="app.workers.tasks.generate_ai_for_new_items")
def generate_ai_for_new_items(limit: int = 20):
    cutoff_ai = _cutoff_utc(settings.ai_not_before_days, settings.ai_not_before)
    skipped_ai_cutoff = 0
    with SessionLocal() as db:
        auto_approved_count = 0
        items = db.scalars(
            select(Item).where(Item.status == ItemStatus.new).order_by(Item.created_at.asc()).limit(limit)
        ).all()

        for it in items:
            # Skip old items (if date known)
            if cutoff_ai and it.published_at:
                try:
                    pub = it.published_at
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=dt.timezone.utc)
                    else:
                        pub = pub.astimezone(dt.timezone.utc)
                    if pub < cutoff_ai:
                        skipped_ai_cutoff += 1
                        it.status = ItemStatus.rejected
                        logger.info(
                            "[cutoff] skipped by AI_NOT_BEFORE item_id=%s url=%s published_at=%s cutoff=%s",
                            it.id,
                            it.url,
                            pub.isoformat(),
                            cutoff_ai.isoformat(),
                        )
                        continue
                except Exception:
                    pass

            # Filter non-theatre
            if not is_theatre_related((it.title or "") + " " + (it.raw_text or "")):
                it.status = ItemStatus.rejected
                continue

            # AI
            try:
                content = generate_post(title=it.title or "", text=it.raw_text or "", url=it.url)
            except Exception as ex:
                # leave as new for retry
                continue

            if content.strip() == "REJECT":
                it.status = ItemStatus.rejected
                continue

            # Create post
            post = Post(
                item_id=it.id,
                tg_text=content,
                moderation_status=ModerationStatus.pending,
                tg_media={},
                style_version="v1",
            )
            if settings.auto_publish_after_ai_selection:
                try:
                    ok, reason = _auto_translate_post_if_needed(post)
                    if not ok:
                        post.moderation_status = ModerationStatus.failed
                        post.editor_notes = (reason or "Auto-translate failed")[:2000]
                    else:
                        post.moderation_status = ModerationStatus.approved
                        auto_approved_count += 1
                except Exception as ex:
                    post.moderation_status = ModerationStatus.failed
                    post.editor_notes = f"Auto-translate exception: {ex}"[:2000]
            db.add(post)
            it.status = ItemStatus.ai_ready

        db.commit()

        logger.info(
            "[ai] batch=%s skipped_ai_cutoff=%s auto_approved=%s cutoff_ai=%s",
            len(items),
            skipped_ai_cutoff,
            auto_approved_count,
            cutoff_ai.isoformat() if cutoff_ai else None,
        )

    if settings.auto_publish_after_ai_selection and auto_approved_count > 0:
        publish_scheduled_posts.delay()

@shared_task(name="app.workers.tasks.publish_scheduled_posts")
def publish_scheduled_posts(batch: int = 10):
    import asyncio
    now = dt.datetime.now(dt.timezone.utc)
    with SessionLocal() as db:
        posts = db.scalars(
            select(Post)
            .where(Post.moderation_status.in_([ModerationStatus.scheduled, ModerationStatus.approved]))
            .where((Post.scheduled_at == None) | (Post.scheduled_at <= now))  # noqa: E711
            .order_by(Post.scheduled_at.asc().nullsfirst(), Post.created_at.asc())
            .limit(batch)
        ).all()

        async def _run():
            lang = (settings.tg_publish_language or "").strip().lower()
            for p in posts:
                if lang == "ru":
                    text = (p.tg_text or "").strip()
                    fail_hint = "Empty tg_text"
                elif lang == "th":
                    text = (p.tg_text_th or "").strip()
                    fail_hint = "Missing Thai text (tg_text_th). Use Translate → Thai in UI."
                elif lang == "en":
                    text = (p.tg_text_en or "").strip()
                    fail_hint = "Missing English text (tg_text_en). Use Translate → English in UI."
                elif lang == "es":
                    text = (p.tg_text_es or "").strip()
                    fail_hint = "Missing Spanish text (tg_text_es). Use Translate → Spanish in UI."
                elif lang == "it":
                    text = (p.tg_text_it or "").strip()
                    fail_hint = "Missing Italian text (tg_text_it). Use Translate → Italian in UI."
                else:
                    text = None
                    fail_hint = f"Unsupported TG_PUBLISH_LANGUAGE: {settings.tg_publish_language}"

                if not text:
                    p.moderation_status = ModerationStatus.failed
                    p.editor_notes = fail_hint[:2000]
                    continue

                try:
                    mid = await send_to_channel(text)
                    p.tg_message_id = mid
                    p.posted_at = dt.datetime.now(dt.timezone.utc)
                    p.moderation_status = ModerationStatus.posted
                except Exception as ex:
                    p.moderation_status = ModerationStatus.failed
                    p.editor_notes = str(ex)[:2000]

        asyncio.run(_run())
        db.commit()

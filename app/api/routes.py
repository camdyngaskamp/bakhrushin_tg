from __future__ import annotations
import datetime as dt
import json
import httpx
import pytz

from fastapi import APIRouter, Depends, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import Post, ModerationStatus, Source, SourceType
from app.ai.translate import translate_ru
from app.config import settings
from app.web.security import login_url, sanitize_next_path

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

TRANSLATION_TARGETS = {
    "th": {"field": "tg_text_th", "label": "Thai"},
    "en": {"field": "tg_text_en", "label": "English"},
    "es": {"field": "tg_text_es", "label": "Spanish"},
    "it": {"field": "tg_text_it", "label": "Italian"},
}

PUBLISH_LANGUAGE_LABELS = {
    "ru": "Russian (RU)",
    "th": "Thai (TH)",
    "en": "English (EN)",
    "es": "Spanish (ES)",
    "it": "Italian (IT)",
}

def _publish_language_label() -> str:
    lang = (settings.tg_publish_language or "ru").lower()
    return PUBLISH_LANGUAGE_LABELS.get(lang, lang.upper())


templates.env.globals["publish_language_label"] = _publish_language_label()

MSK = pytz.timezone("Europe/Moscow")

UA = {"User-Agent": "BakhrushinMuseumNewsBot/1.0 (+https://www.bakhrushinmuseum.ru/)"}


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    posts = db.scalars(
        select(Post).where(Post.moderation_status.in_([ModerationStatus.pending, ModerationStatus.approved, ModerationStatus.scheduled]))
        .order_by(Post.created_at.desc())
        .limit(50)
    ).all()

    pending_count = db.scalar(select(func.count()).select_from(Post).where(Post.moderation_status == ModerationStatus.pending))
    approved_count = db.scalar(select(func.count()).select_from(Post).where(Post.moderation_status == ModerationStatus.approved))
    scheduled_count = db.scalar(select(func.count()).select_from(Post).where(Post.moderation_status == ModerationStatus.scheduled))

    return templates.TemplateResponse("index.html", {
        "request": request,
        "posts": posts,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "scheduled_count": scheduled_count,
        "pytz": pytz,
        "MSK": MSK,
        "web_password_set": bool(settings.web_password),
    })

@router.get("/posts/{post_id}", response_class=HTMLResponse)
def get_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if not post:
        return HTMLResponse("Not found", status_code=404)
    _ = post.item
    publish_lang = (settings.tg_publish_language or "ru").lower()
    publish_target = TRANSLATION_TARGETS.get(publish_lang)
    return templates.TemplateResponse(
        "post.html",
        {
            "request": request,
            "post": post,
            "pytz": pytz,
            "MSK": MSK,
            "web_password_set": bool(settings.web_password),
            "publish_lang": publish_lang,
            "publish_target": publish_target,
            "publish_language_label": PUBLISH_LANGUAGE_LABELS.get(publish_lang, publish_lang.upper()),
        },
    )



@router.post("/posts/{post_id}/translate/{lang_code}")
def translate_post_language(post_id: int, lang_code: str, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if not post:
        return HTMLResponse("Not found", status_code=404)

    lang = (lang_code or "").lower()
    target = TRANSLATION_TARGETS.get(lang)
    if not target:
        return HTMLResponse("Unsupported language", status_code=400)

    ru = (post.tg_text or "").strip()
    if not ru:
        post.editor_notes = f"Cannot translate to {target['label']}: empty tg_text"
        db.commit()
        return RedirectResponse(url=f"/posts/{post_id}", status_code=303)

    try:
        translated = translate_ru(ru, target_lang=lang, style=settings.tg_translation_style)
        setattr(post, target["field"], translated or None)
    except Exception as ex:
        post.editor_notes = (f"{target['label']} translation error: {ex}")[:2000]
    db.commit()
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)

def _normalize_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


@router.post("/posts/{post_id}/update")
def update_post(
    post_id: int,
    tg_text: str = Form(...),
    tg_text_th: str = Form(""),
    tg_text_en: str = Form(""),
    tg_text_es: str = Form(""),
    tg_text_it: str = Form(""),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post:
        return HTMLResponse("Not found", status_code=404)
    post.tg_text = tg_text
    post.tg_text_th = _normalize_or_none(tg_text_th)
    post.tg_text_en = _normalize_or_none(tg_text_en)
    post.tg_text_es = _normalize_or_none(tg_text_es)
    post.tg_text_it = _normalize_or_none(tg_text_it)
    db.commit()
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)

@router.post("/posts/{post_id}/reject")
def reject_post(
    post_id: int,
    tg_text: str = Form(None),
    tg_text_th: str = Form(None),
    tg_text_en: str = Form(None),
    tg_text_es: str = Form(None),
    tg_text_it: str = Form(None),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post:
        return HTMLResponse("Not found", status_code=404)
    if tg_text is not None:
        post.tg_text = tg_text
    if tg_text_th is not None:
        post.tg_text_th = _normalize_or_none(tg_text_th)
    if tg_text_en is not None:
        post.tg_text_en = _normalize_or_none(tg_text_en)
    if tg_text_es is not None:
        post.tg_text_es = _normalize_or_none(tg_text_es)
    if tg_text_it is not None:
        post.tg_text_it = _normalize_or_none(tg_text_it)
    post.moderation_status = ModerationStatus.rejected
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@router.post("/posts/{post_id}/approve")
def approve_post(
    post_id: int,
    tg_text: str = Form(None),
    tg_text_th: str = Form(None),
    tg_text_en: str = Form(None),
    tg_text_es: str = Form(None),
    tg_text_it: str = Form(None),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post:
        return HTMLResponse("Not found", status_code=404)
    if tg_text is not None:
        post.tg_text = tg_text
    if tg_text_th is not None:
        post.tg_text_th = _normalize_or_none(tg_text_th)
    if tg_text_en is not None:
        post.tg_text_en = _normalize_or_none(tg_text_en)
    if tg_text_es is not None:
        post.tg_text_es = _normalize_or_none(tg_text_es)
    if tg_text_it is not None:
        post.tg_text_it = _normalize_or_none(tg_text_it)
    post.moderation_status = ModerationStatus.approved
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@router.post("/posts/{post_id}/schedule")
def schedule_post(
    post_id: int,
    tg_text: str = Form(None),
    tg_text_th: str = Form(None),
    tg_text_en: str = Form(None),
    tg_text_es: str = Form(None),
    tg_text_it: str = Form(None),
    scheduled_at: str = Form(...),
    db: Session = Depends(get_db),
):
    post = db.get(Post, post_id)
    if not post:
        return HTMLResponse("Not found", status_code=404)
    if tg_text is not None:
        post.tg_text = tg_text
    if tg_text_th is not None:
        post.tg_text_th = _normalize_or_none(tg_text_th)
    if tg_text_en is not None:
        post.tg_text_en = _normalize_or_none(tg_text_en)
    if tg_text_es is not None:
        post.tg_text_es = _normalize_or_none(tg_text_es)
    if tg_text_it is not None:
        post.tg_text_it = _normalize_or_none(tg_text_it)

    # Accept 'YYYY-MM-DD HH:MM' in Moscow time (MSK)
    try:
        local = dt.datetime.strptime(scheduled_at.strip(), "%Y-%m-%d %H:%M")
        local = MSK.localize(local)
        when = local.astimezone(dt.timezone.utc)
    except Exception:
        return HTMLResponse("Bad scheduled_at format. Use: YYYY-MM-DD HH:MM (MSK)", status_code=400)

    post.scheduled_at = when
    post.moderation_status = ModerationStatus.scheduled
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/sources", response_class=HTMLResponse)
def list_sources(request: Request, q: str | None = None, status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Source).order_by(Source.id.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Source.name.ilike(like)) | (Source.url.ilike(like)))
    if status == "enabled":
        stmt = stmt.where(Source.enabled == True)  # noqa: E712
    elif status == "disabled":
        stmt = stmt.where(Source.enabled == False)  # noqa: E712

    sources = db.scalars(stmt.limit(200)).all()

    total_count = db.scalar(select(func.count()).select_from(Source))
    enabled_count = db.scalar(select(func.count()).select_from(Source).where(Source.enabled == True))  # noqa: E712
    disabled_count = db.scalar(select(func.count()).select_from(Source).where(Source.enabled == False))  # noqa: E712

    return templates.TemplateResponse("sources.html", {
        "request": request,
        "sources": sources,
        "q": q,
        "status": status,
        "total_count": total_count,
        "enabled_count": enabled_count,
        "disabled_count": disabled_count,
        "web_password_set": bool(settings.web_password),
    })


@router.post("/sources/create")
def create_source(
    name: str = Form(...),
    type: str = Form(...),
    url: str = Form(...),
    db: Session = Depends(get_db),
):
    src = Source(
        name=name.strip(),
        type=SourceType(type),
        url=url.strip(),
        enabled=True,
        parser_config={},
    )
    db.add(src)
    db.commit()
    return RedirectResponse(url="/sources", status_code=303)


@router.get("/sources/{source_id}", response_class=HTMLResponse)
def edit_source(source_id: int, request: Request, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        return HTMLResponse("Not found", status_code=404)
    parser_config_json = json.dumps(src.parser_config or {}, ensure_ascii=False, indent=2)
    return templates.TemplateResponse("source_edit.html", {
        "request": request,
        "source": src,
        "parser_config_json": parser_config_json,
        "error": None,
        "web_password_set": bool(settings.web_password),
    })


@router.post("/sources/{source_id}/update", response_class=HTMLResponse)
def update_source(
    source_id: int,
    request: Request,
    name: str = Form(...),
    type: str = Form(...),
    url: str = Form(...),
    enabled: str | None = Form(None),
    parser_config: str = Form(""),
    db: Session = Depends(get_db),
):
    src = db.get(Source, source_id)
    if not src:
        return HTMLResponse("Not found", status_code=404)

    # Validate parser_config JSON
    try:
        cfg = json.loads(parser_config.strip() or "{}")
        if not isinstance(cfg, dict):
            raise ValueError("parser_config must be a JSON object")
    except Exception as ex:
        parser_config_json = parser_config
        return templates.TemplateResponse("source_edit.html", {
            "request": request,
            "source": src,
            "parser_config_json": parser_config_json,
            "error": f"Invalid parser_config JSON: {ex}",
        })

    src.name = name.strip()
    src.type = SourceType(type)
    src.url = url.strip()
    src.enabled = enabled is not None
    src.parser_config = cfg

    db.commit()
    return RedirectResponse(url="/sources", status_code=303)



@router.post("/sources/{source_id}/test")
def test_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        return HTMLResponse("Not found", status_code=404)

    now = dt.datetime.now(dt.timezone.utc)
    status_code: int | None = None
    err: str | None = None

    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=UA) as client:
            r = client.get(src.url)
            status_code = r.status_code
    except Exception as ex:
        err = str(ex)

    src.last_status_code = status_code
    src.last_error = err
    src.last_checked_at = now
    db.commit()
    return RedirectResponse(url="/sources", status_code=303)

@router.post("/sources/{source_id}/toggle")
def toggle_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        return HTMLResponse("Not found", status_code=404)
    src.enabled = not bool(src.enabled)
    db.commit()
    return RedirectResponse(url="/sources", status_code=303)


@router.post("/sources/{source_id}/delete")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(Source, source_id)
    if not src:
        return HTMLResponse("Not found", status_code=404)
    db.delete(src)
    db.commit()
    return RedirectResponse(url="/sources", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    error: str | None = None,
    next_path: str | None = Query(None, alias="next"),
):
    """Страница входа в систему."""
    target = sanitize_next_path(next_path)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "next_path": target,
    })


@router.post("/login")
async def login(
    request: Request,
    password: str = Form(...),
    next_path: str = Form("/", alias="next"),
):
    """Обработка входа в систему."""
    from app.middleware.auth import set_auth_cookie, _check_rate_limit, _clear_rate_limit
    
    target = sanitize_next_path(next_path)
    # Получаем IP клиента
    client_ip = request.client.host if request.client else "unknown"
    
    # Проверка rate limit
    allowed, rate_error = _check_rate_limit(client_ip)
    if not allowed:
        return RedirectResponse(
            url=login_url(error=rate_error, next_path=target),
            status_code=303
        )
    
    response = RedirectResponse(url=target, status_code=303)
    is_secure = request.url.scheme == "https"
    success, error, session_token = await set_auth_cookie(response, password, is_secure=is_secure)
    
    if success:
        # Очищаем rate limit после успешной авторизации
        _clear_rate_limit(client_ip)
        # Сохраняем токен в response state для использования при выходе
        response.headers["X-Session-Token"] = session_token or ""
        return response
    
    return RedirectResponse(url=login_url(error=error, next_path=target), status_code=303)


@router.post("/logout")
async def logout(request: Request):
    """Выход из системы."""
    from app.middleware.auth import clear_auth_cookie
    
    # Получаем токен из cookie запроса
    session_token = request.cookies.get("web_session_token")
    
    response = RedirectResponse(url="/login", status_code=303)
    await clear_auth_cookie(response, session_token)
    return response

from __future__ import annotations

import secrets
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.web.security import sanitize_next_path, login_url

logger = logging.getLogger(__name__)

# Rate limiting storage (in-memory, resets on app restart)
# Format: {ip: {"count": int, "first_attempt": float}}
_login_attempts: dict[str, dict] = {}


def _check_rate_limit(client_ip: str, max_attempts: int = 5, window_seconds: int = 300) -> tuple[bool, str | None]:
    """
    Проверка rate limit для защиты от brute-force атак.
    
    Args:
        client_ip: IP адрес клиента
        max_attempts: Максимальное количество попыток
        window_seconds: Размер окна проверки в секундах
    
    Returns:
        tuple: (allowed, error_message)
    """
    current_time = time.time()
    
    if client_ip not in _login_attempts:
        _login_attempts[client_ip] = {"count": 1, "first_attempt": current_time}
        return True, None
    
    attempt_data = _login_attempts[client_ip]
    
    # Если окно времени истекло, сбрасываем счетчик
    if current_time - attempt_data["first_attempt"] > window_seconds:
        _login_attempts[client_ip] = {"count": 1, "first_attempt": current_time}
        return True, None
    
    # Проверяем количество попыток
    if attempt_data["count"] >= max_attempts:
        remaining = int(window_seconds - (current_time - attempt_data["first_attempt"]))
        return False, f"Слишком много попыток. Попробуйте через {remaining} сек."
    
    attempt_data["count"] += 1
    return True, None


def _clear_rate_limit(client_ip: str) -> None:
    """Очистка rate limit после успешной авторизации."""
    if client_ip in _login_attempts:
        del _login_attempts[client_ip]


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware для проверки авторизации веб-интерфейса."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Если пароль не задан, пропускаем проверку (для dev режима)
        if not settings.web_password:
            return await call_next(request)
        
        # Исключаем страницу логина и логаут из проверки
        if request.url.path in ["/login", "/logout"]:
            return await call_next(request)
        
        # Исключаем статические файлы и API endpoints
        if request.url.path.startswith(("/static/", "/api/")):
            return await call_next(request)
        
        # Проверяем session token в cookie
        session_token = request.cookies.get("web_session_token")
        
        if session_token:
            # Проверяем токен в Redis
            try:
                from app.db.session import redis_client
                if redis_client:
                    key = f"session:{session_token}"
                    user_id = redis_client.get(key)
                    if user_id:
                        # Обновляем TTL токена
                        redis_client.expire(key, 3600 * 24 * 7)
                        # Передаём запрос дальше вне try/except — ошибки приложения
                        # не должны перехватываться как ошибки авторизации
                        return await call_next(request)
            except Exception as e:
                logger.warning(f"Redis session check failed: {e}")
                # Redis недоступен — пропускаем запрос, не блокируем пользователя
                return await call_next(request)
        
        # Если не авторизован, перенаправляем на логин
        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        next_path = sanitize_next_path(next_path)
        if next_path in {"/login", "/logout"}:
            next_path = "/"
        return RedirectResponse(url=login_url(next_path=next_path), status_code=303)


async def authenticate_user(password: str) -> bool:
    """Проверка пароля пользователя."""
    return password == settings.web_password


async def set_auth_cookie(response: Response, password: str, is_secure: bool = False) -> tuple[bool, str | None, str | None]:
    """
    Установка cookie для авторизации.
    
    Args:
        response: HTTP response объект для установки cookie
        password: Пароль пользователя
        is_secure: True только если соединение идёт по HTTPS
    
    Returns:
        tuple: (success, error_message, session_token or None)
    """
    if not await authenticate_user(password):
        return False, "Неверный пароль", None
    
    # Генерируем случайный токен сессии
    session_token = secrets.token_urlsafe(32)
    
    try:
        from app.db.session import redis_client
        if redis_client:
            # Сохраняем токен в Redis с TTL 7 дней
            redis_client.setex(
                f"session:{session_token}",
                3600 * 24 * 7,
                "authenticated"
            )
            logger.info("Session created in Redis")
        else:
            logger.warning("Redis client not available, using fallback mode")
    except Exception as e:
        logger.warning(f"Failed to create session in Redis: {e}")
    
    # Устанавливаем cookie с токеном.
    # Флаг Secure=True только при HTTPS — при HTTP браузер не отправляет Secure cookie
    # обратно на сервер, что приводит к бесконечному циклу входа.
    response.set_cookie(
        key="web_session_token",
        value=session_token,
        max_age=3600 * 24 * 7,
        httponly=True,
        samesite="lax",
        secure=is_secure,
    )
    
    return True, None, session_token


async def clear_auth_cookie(response: Response, session_token: str | None = None) -> None:
    """Очистка cookie для выхода из системы."""
    response.delete_cookie("web_session_token")
    
    try:
        from app.db.session import redis_client
        if redis_client and session_token:
            # Удаляем токен из Redis
            redis_client.delete(f"session:{session_token}")
    except Exception as e:
        logger.warning(f"Failed to clear session in Redis: {e}")

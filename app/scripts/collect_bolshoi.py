"""Manual collection of the Bolshoi source with readable access errors."""
import datetime as dt
import logging
import sys

import httpx

from app.collectors.browser import BrowserFetchError


def collect_with_status(db, source, collector):
    """Return an exit code; roll back news before persisting failure metadata."""
    try:
        collector(db, source)
    except (httpx.HTTPStatusError, BrowserFetchError) as exc:
        db.rollback()
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        source.last_status_code = status
        source.last_error = str(exc)
        source.last_checked_at = dt.datetime.now(dt.timezone.utc)
        source.fail_streak = (source.fail_streak or 0) + 1 if status in (401, 403) else 0
        db.commit()
        if status in (401, 403):
            print(f'Сбор остановлен: сайт Большого театра отказал в доступе (HTTP {status}).', file=sys.stderr)
            print('Cookies могли истечь или не подойти для этого подключения.', file=sys.stderr)
            print('Получите свежие cookies в обычном Chrome, импортируйте их и перенесите bolshoi.json на сервер.', file=sys.stderr)
            print('Инструкция: docs/CHROME_COOKIES_TO_SERVER.md', file=sys.stderr)
            print('Увеличение таймаута не устраняет отказ. Повторите сбор после проверки доступа.', file=sys.stderr)
            exit_code = 2
        else:
            print('Сбор остановлен: не удалось загрузить страницу источника.', file=sys.stderr)
            exit_code = 3
        print(f'Диагностика: {exc}', file=sys.stderr)
        print('Новые материалы этого запуска не сохранены. Ошибка записана в карточку источника.', file=sys.stderr)
        return exit_code

    source.last_status_code = 200
    source.last_error = None
    source.last_checked_at = dt.datetime.now(dt.timezone.utc)
    source.fail_streak = 0
    db.commit()
    return 0


def main():
    from sqlalchemy import select, func
    from app.db.session import SessionLocal
    from app.db.models import Source, SourceType, Item
    from app.workers.tasks import _collect_html_source

    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        sources = db.scalars(select(Source).where(Source.url.in_([
            'https://bolshoi.ru/news', 'https://bolshoi.ru/news/',
        ]))).all()
        if not sources:
            raise SystemExit('Источник Большого театра не найден')
        if len(sources) != 1:
            raise SystemExit('Найдено несколько источников: устраните дубликаты перед сбором')
        source = sources[0]
        if source.type != SourceType.html:
            raise SystemExit('Источник должен иметь тип html')

        def item_count():
            return db.scalar(select(func.count(Item.id)).where(Item.source_id == source.id))

        before = item_count()
        print(f'Собираем: {source.name}, ID={source.id}', flush=True)
        exit_code = collect_with_status(db, source, _collect_html_source)
        if exit_code:
            return exit_code
        print('Добавлено материалов:', item_count() - before)
        print('Статусы всех материалов этого источника:')
        for status, count in db.execute(
            select(Item.status, func.count(Item.id))
            .where(Item.source_id == source.id).group_by(Item.status)
        ):
            print(f'  {status.value}: {count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

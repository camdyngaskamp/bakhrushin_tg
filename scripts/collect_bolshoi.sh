#!/usr/bin/env bash
# Collect only Bolshoi news using its stored source configuration and cookies.
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Использование: $0"
    echo "Собирает только новости Большого театра в БД через celery_worker."
    echo "Использует parser_config источника и сохранённую браузерную сессию."
    echo "Работает также для отключённого источника. Не запускает AI или публикацию."
    exit 0
fi
if [[ $# -ne 0 ]]; then
    echo "Неизвестные параметры. Используйте --help." >&2
    exit 2
fi

BOLSHOI_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$BOLSHOI_SCRIPT_DIR/.."

if ! command -v docker >/dev/null 2>&1; then
    echo "Не найден docker. Запустите скрипт на сервере с Docker Compose." >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "Недоступен docker compose. Проверьте установку Compose." >&2
    exit 1
fi

# The container must already be running. Do not start or stop other services.
docker compose exec -T celery_worker python - <<'PY'
import datetime as dt
import logging

from sqlalchemy import select, func
from app.db.session import SessionLocal
from app.db.models import Source, SourceType, Item
from app.workers.tasks import _collect_html_source

logging.basicConfig(level=logging.INFO)

with SessionLocal() as db:
    sources = db.scalars(
        select(Source).where(
            Source.url.in_([
                'https://bolshoi.ru/news',
                'https://bolshoi.ru/news/',
            ])
        )
    ).all()
    if not sources:
        raise SystemExit('Источник Большого театра не найден')
    if len(sources) != 1:
        raise SystemExit('Найдено несколько источников: устраните дубликаты перед сбором')
    source = sources[0]
    if source.type != SourceType.html:
        raise SystemExit('Источник должен иметь тип html')

    def item_count():
        return db.scalar(
            select(func.count(Item.id)).where(Item.source_id == source.id)
        )

    before = item_count()
    print(f'Собираем: {source.name}, ID={source.id}', flush=True)

    _collect_html_source(db, source)

    source.last_status_code = 200
    source.last_error = None
    source.last_checked_at = dt.datetime.now(dt.timezone.utc)
    source.fail_streak = 0
    db.commit()

    print('Добавлено материалов:', item_count() - before)
    print('Статусы всех материалов этого источника:')
    for status, count in db.execute(
        select(Item.status, func.count(Item.id))
        .where(Item.source_id == source.id)
        .group_by(Item.status)
    ):
        print(f'  {status.value}: {count}')
PY

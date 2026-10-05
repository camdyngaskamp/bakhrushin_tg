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
docker compose exec -T celery_worker python -m app.scripts.collect_bolshoi

# Bakhrushin Museum News — Telegram automation

Automated system for collecting theatre-related news from the internet, generating Telegram-ready summaries with AI (**OpenAI** by default, with support for OpenAI-compatible providers), moderating, and publishing to the Telegram channel **@bakhrushinmuseum_news**.

## What it does

- Collects news from **RSS** and **HTML** sources
- Stores data in **PostgreSQL** (with Alembic migrations)
- Generates summaries via **OpenAI** (or any OpenAI-compatible provider)
- Provides a **web moderation panel** (FastAPI + Jinja2)
- Publishes to Telegram via **aiogram**
- Runs background jobs via **Celery + Redis + Celery Beat**

Pipeline:

`Sources → Items → AI → Posts (pending) → Approve/Schedule → Telegram`

Optional full automation mode:

`Sources → Items → AI → Auto-translate → Auto-approve → Telegram`

## Requirements

- Docker + Docker Compose (Compose v2)
- Ubuntu 22.04 / 24.04 recommended

## Quick start

### 1) Configure environment

```bash
cp .env.example .env
```

Fill at least:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL` (default: `@bakhrushinmuseum_news`)
- `AI_API_KEY`

AI provider is configured in `.env`:

- `AI_PROVIDER=openai`
- `AI_BASE_URL=https://api.openai.com/v1`
- `AI_API_KEY=...`

For OpenAI-compatible providers, set `AI_PROVIDER` to any provider label and point `AI_BASE_URL` to that provider's OpenAI-compatible endpoint.

### 2) Run services

```bash
docker compose up -d --build
```

### 3) Initialize database

```bash
docker compose exec api alembic upgrade head
```

### 4) Seed initial sources

```bash
docker compose exec api python -m app.scripts.seed_sources
```

### 5) Open web panel

- Posts moderation: http://localhost:8000/
- Sources management: http://localhost:8000/sources

## Telegram setup

1. Create a bot via **@BotFather** and set `TELEGRAM_BOT_TOKEN`.
2. Add the bot as **admin** to the channel **@bakhrushinmuseum_news** with **posting rights**.
3. Set `TELEGRAM_CHANNEL=@bakhrushinmuseum_news`.

## Moderation & publishing

Statuses:

- `pending` — waiting for moderation
- `approved` — **publish ASAP** (publisher will pick it up)
- `scheduled` — publish at `scheduled_at`
- `posted` — published successfully
- `failed` — publishing failed (see `editor_notes`)

### Optional: fully automatic translation + publishing

Enable these `.env` flags:

```env
AUTO_PUBLISH_AFTER_AI_SELECTION=true
AUTO_TRANSLATE_AFTER_AI_SELECTION=true
```

Behavior:

- right after AI summary generation, post is automatically translated to `TG_PUBLISH_LANGUAGE` (for non-`ru` languages);
- post is automatically marked as `approved`;
- publisher task is triggered automatically, so no manual moderation is required.

### Approve publishes immediately

- Open a post → optionally edit text → **Approve**

### Schedule uses Moscow time (MSK)

- Open a post → set `scheduled_at` in **MSK** format `YYYY-MM-DD HH:MM` → **Approve + Schedule**
- DB stores schedule in UTC; UI accepts and displays MSK.

## Sources management

Open: http://localhost:8000/sources

You can:

- add new sources (type: `rss` / `html`)
- edit `parser_config` (JSON)
- enable/disable sources
- delete sources
- **Test** a source URL (stores `last_status_code`, `last_checked_at`, `last_error`)

### When a source returns 401/403

Some sites block bots. Use the **Test** button and disable such sources, or switch to a different URL/feed.

## Cutoff filters (avoid old news)

To prevent collecting or AI-processing old items, use sliding window cutoffs:

```env
NEWS_NOT_BEFORE_DAYS=7
AI_NOT_BEFORE_DAYS=7
```

Rules:

- `NEWS_NOT_BEFORE_DAYS`: collector skips items older than N days **if the item date is known**.
- `AI_NOT_BEFORE_DAYS`: AI step skips items older than N days **if the item date is known**.
- Items without a date are not blocked by cutoffs.

Collector and AI steps log skipped items as:

- `[cutoff] skipped by NEWS_NOT_BEFORE ...`
- `[cutoff] skipped by AI_NOT_BEFORE ...`

## Operations

### Check services

```bash
docker compose ps
```

### Logs

```bash
# API / Web panel
docker compose logs -f api

# Background worker
docker compose logs -f celery_worker

# Scheduler
docker compose logs -f celery_beat
```

### Run jobs manually

```bash
# collect sources now
docker compose exec api python -c "from app.workers.tasks import collect_all_sources; collect_all_sources()"

# generate AI posts now
docker compose exec api python -c "from app.workers.tasks import generate_ai_for_new_items; generate_ai_for_new_items(20)"

# publish approved/scheduled now
docker compose exec api python -c "from app.workers.tasks import publish_scheduled_posts; publish_scheduled_posts(10)"
```

## Backup

### Dump database

```bash
docker compose exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

### Restore

```bash
docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB" < backup.sql
```

## Troubleshooting

### "Received unregistered task" in celery_worker

This means the worker did not import tasks. In this project it is fixed by importing `app.workers.tasks` in `app/workers/celery_app.py`.

Restart:

```bash
docker compose restart celery_worker celery_beat
```

### Port 6379 already in use

Redis port conflict on host. Either stop local Redis, or remove port mapping for Redis in `docker-compose.yml`.

### Alembic errors about sqlalchemy.url

This project uses `migrations/env.py` to load `DATABASE_URL` from `.env` and sets `configuration["sqlalchemy.url"]` at runtime.

## Project structure

- `app/api/` — web routes
- `app/templates/` — Jinja2 templates
- `app/collectors/` — RSS/HTML collection
- `app/parsers/` — text extraction
- `app/ai/` — AI summarization
- `app/workers/` — Celery tasks
- `app/tg/` — Telegram sender
- `migrations/` — Alembic migrations

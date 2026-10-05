# Перенос cookies Большого театра из Chrome на рабочий сервер

Проверенный на локальном компьютере сценарий: новости открываются в обычном
Chrome, импорт его cookies позволяет читать список и статью через скрипт,
а сохранённая сессия работает также в Chromium без окна браузера. Поэтому
устанавливать Google Chrome на сервер для этого сценария не нужно: используйте
Chromium из существующего Docker-образа.

Перенос на другой IP проверяется отдельно. Успешный локальный тест не гарантирует
доступа с сервера; cookies могут быстро истекать или зависеть от окружения.
Переносите сессию сразу после успешной проверки.

## 1. Получить cookies на компьютере с Chrome

Все локальные команды выполняйте из корня проекта с обновлённым кодом.

1. Откройте `https://bolshoi.ru/news` в обычном Google Chrome.
2. Нажмите F12 или Ctrl+Shift+I → **Network / Сеть**. Включите **Preserve log**
   и **Disable cache**, оставьте DevTools открытым и обновите страницу.
3. Найдите итоговый запрос страницы с типом **Document / doc** и статусом **200**.
   Если видите `301`, посмотрите **Response Headers → Location** и найдите запрос
   после перенаправления. Если видите `304`, проверьте, что Disable cache включён,
   и снова обновите страницу. Нужен свежий успешный ответ, а не копия из кеша.
4. В **Headers → Request Headers** этого запроса скопируйте значение **Cookie**.
   Не копируйте Set-Cookie, весь HAR или команду cURL. Если Cookie отсутствует,
   дождитесь появления новостей и повторите обновление.

Подготовьте локальный приватный файл:

```bash
umask 077
mkdir -p .browser-state
touch .browser-state/bolshoi-cookie-header.txt
chmod 600 .browser-state/bolshoi-cookie-header.txt
```

Откройте файл в текстовом редакторе и вставьте значение одной строкой:
`name=value; other=value`. Префикс `Cookie:` допустим. Не вставляйте cookies в
командную строку или чат. Каталог `.browser-state` исключён из Git и Docker-образа.

## 2. Импортировать и проверить сессию

На том же компьютере выполните:

```bash
.venv/bin/python -m app.scripts.browser_session \
  --url https://bolshoi.ru/news \
  --name bolshoi \
  --channel chrome \
  --cookies-file .browser-state/bolshoi-cookie-header.txt \
  --wait-selector "a[href*='/news/']"
```

При успехе появятся сообщения о числе импортированных cookies и сохранении
`.browser-state/bolshoi.json`. В этом режиме нажимать Enter не требуется.
При отказе сайт не открылся; файл предыдущей сессии не заменяется.

Проверьте сохранённую сессию в Chromium и извлечение первой статьи:

```bash
.venv/bin/python - <<'PY'
from app.collectors.browser import browser_fetcher
from app.collectors.html import fetch_html_entries
from app.parsers.extract import extract_main_text

config = {
    'fetch_mode': 'browser',
    'browser_channel': 'chromium',
    'browser_state_name': 'bolshoi',
    'browser_wait_selector': "a[href*='/news/']",
    'include_regex': [r'bolshoi\.ru/(ru/|en/)?news/'],
    'exclude_regex': [r'/news/?$'],
    'max_items': 3,
}
with browser_fetcher(config) as fetcher:
    entries = fetch_html_entries('https://bolshoi.ru/news', config, fetcher=fetcher)
    assert entries, 'Ссылки не найдены'
    text, _ = extract_main_text(entries[0]['url'], fetcher=fetcher)
    assert text.strip(), 'Пустой текст статьи'
    print('Найдено ссылок:', len(entries))
    print('Статья:', entries[0]['url'])
    print('Длина текста:', len(text))
PY
```

Эта команда не пишет новости в БД, не вызывает AI и не публикует в Telegram.
Непустой текст подтверждает извлечение, но его полноту нужно оценить отдельно.
Если проверки прошли, на сервер переносите **только `bolshoi.json`**, а не файл
сырого заголовка или профиль Chrome.

## 3. Передать файл по SSH

На локальном компьютере замените `USER@SERVER` своим SSH-адресом:

```bash
ssh USER@SERVER 'umask 077; mkdir -p .browser-state-upload; chmod 700 .browser-state-upload'
scp .browser-state/bolshoi.json USER@SERVER:.browser-state-upload/bolshoi.json
ssh USER@SERVER 'chmod 600 .browser-state-upload/bolshoi.json'
```

Временный каталог находится в домашнем каталоге SSH-пользователя и доступен
только ему. Содержимое файла сессии не выводите в терминал и не добавляйте в Git.

## 4. Установить сессию на рабочем сервере

Сначала отключите источник Большого театра в веб-панели. Перейдите в каталог
рабочего проекта. Остановите планировщик, worker и API, чтобы текущий сбор или
кнопка «Тест» не перезаписали сессию во время установки:

```bash
cd /путь/к/bakhrushin_tg
docker compose stop celery_beat
docker compose stop -t 300 celery_worker api
```

Убедитесь, что текущие задачи завершились. Если рабочий код ещё не обновлён,
получите изменения (при чистой рабочей директории):

```bash
git pull --ff-only
```

Для этих изменений миграции не нужны. Если Playwright и Chromium уже установлены
в контейнерах, пересборка образов не требуется. Если ещё нет — следуйте
[полной инструкции обновления](UPDATE_BROWSER_COLLECTOR.md).

Сохраните прежнюю сессию, если она существует, и установите новую:

```bash
sudo install -d -m 700 .browser-state
if sudo test -f .browser-state/bolshoi.json; then
  sudo cp -p .browser-state/bolshoi.json .browser-state/bolshoi.previous.json
fi
sudo install -m 600 "$HOME/.browser-state-upload/bolshoi.json" .browser-state/bolshoi.json
docker compose up -d --no-deps api celery_worker
```

Текущий Compose запускает сервисы от root, поэтому файлы root с правами 600
доступны контейнерам. Если в вашем развёртывании задан другой пользователь,
назначьте владельца, доступного API и worker. Каталог проекта смонтирован в
контейнеры как `/app`, поэтому файл автоматически доступен по адресу
`/app/.browser-state/bolshoi.json`. Не копируйте его внутрь образа через Dockerfile.

## 5. Настроить источник и проверить доступ с сервера

В веб-панели отредактируйте `parser_config` Большого театра. Добавьте или обновите
эти поля, сохранив существующие фильтры ссылок:

```json
{
  "fetch_mode": "browser",
  "browser_channel": "chromium",
  "browser_state_name": "bolshoi",
  "browser_timeout_ms": 45000,
  "browser_wait_selector": "a[href*='/news/']"
}
```

Не включайте источник до проверки. Нажмите «Тест», затем выполните из каталога
проекта на сервере:

```bash
docker compose exec -T celery_worker python - <<'PY'
from app.collectors.browser import browser_fetcher
from app.collectors.html import fetch_html_entries
from app.parsers.extract import extract_main_text

config = {
    'fetch_mode': 'browser',
    'browser_channel': 'chromium',
    'browser_state_name': 'bolshoi',
    'browser_timeout_ms': 45000,
    'browser_wait_selector': "a[href*='/news/']",
    'include_regex': [r'bolshoi\.ru/(ru/|en/)?news/'],
    'exclude_regex': [r'/news/?$'],
    'same_domain': True,
    'max_items': 3,
}
with browser_fetcher(config) as fetcher:
    entries = fetch_html_entries('https://bolshoi.ru/news', config, fetcher=fetcher)
    assert entries, 'Ссылки не найдены'
    text, _ = extract_main_text(entries[0]['url'], fetcher=fetcher)
    assert text.strip(), 'Пустой текст статьи'
    print('Найдено ссылок:', len(entries))
    print('Статья:', entries[0]['url'])
    print('Длина текста:', len(text))
PY
```

При успешном тесте списка и статьи включите источник в панели. Если снова
появился Forbidden, оставьте его отключённым: перенесённые cookies не обеспечили
доступ с сервера. Увеличение таймаута не устраняет отказ сайта.

После проверки сервисов возобновите расписание, даже если Большой театр пришлось
оставить отключённым — другие источники могут продолжать работу:

```bash
docker compose up -d --no-deps celery_beat
docker compose ps
docker compose logs --tail=100 celery_worker celery_beat
```

Включение Beat возобновляет все его задачи, включая AI и публикацию одобренных
постов. Следите за состоянием источника после следующих сборов: один успешный
запрос не доказывает долгосрочную работу. При истечении допуска повторите экспорт
из Chrome, импорт и перенос; автоматическое сохранение не гарантирует продление
допуска на стороне сайта.

Удалите временные файлы с cookies после завершения переноса:

- на компьютере — `.browser-state/bolshoi-cookie-header.txt`;
- на сервере — `$HOME/.browser-state-upload/bolshoi.json`.

Рабочий `.browser-state/bolshoi.json` оставьте: он нужен сборщику. Резервная
сессия `bolshoi.previous.json` также содержит cookies; храните её с правами 600
и удалите, когда откат больше не нужен. Для отката файла сначала снова остановите
API и worker, восстановите резервную копию и повторите проверку.

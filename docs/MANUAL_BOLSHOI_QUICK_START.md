# Краткая инструкция: ручной сбор новостей Большого театра

Все команды выполняйте из каталога проекта на соответствующем компьютере.

## 1. Найти и сохранить cookies

Откройте новости Большого театра в обычном Chrome, затем **F12 → Network**.
Включите **Disable cache** и обновите страницу. Выберите последний запрос типа
`document` со статусом `200`, который загрузил страницу новостей.

Скопируйте **Headers → Request Headers → Cookie** и сохраните значение одной
строкой в `.browser-state/bolshoi-cookie-header.txt`. Не копируйте Set-Cookie.
Если каталога ещё нет, подготовьте его и файл:

```bash
umask 077
mkdir -p .browser-state
touch .browser-state/bolshoi-cookie-header.txt
chmod 600 .browser-state/bolshoi-cookie-header.txt
```

После этого вставьте cookies в файл через текстовый редактор.

## 2. Сразу создать сессию

Пока cookies не истекли, выполните на компьютере с Chrome:

```bash
.venv/bin/python -m app.scripts.browser_session \
  --url https://bolshoi.ru/news \
  --name bolshoi \
  --channel chrome \
  --cookies-file .browser-state/bolshoi-cookie-header.txt \
  --wait-selector "a[href*='/news/']"
```

Дождитесь сообщения:

```text
Сессия bolshoi сохранена в .browser-state/bolshoi.json
```

## 3. Перенести bolshoi.json на сервер

Замените `USER@SERVER` своим SSH-адресом. На локальном компьютере:

```bash
ssh USER@SERVER 'umask 077; mkdir -p .browser-state-upload; chmod 700 .browser-state-upload'
scp .browser-state/bolshoi.json USER@SERVER:.browser-state-upload/bolshoi.json
ssh USER@SERVER 'chmod 600 .browser-state-upload/bolshoi.json'
```

На сервере перейдите в каталог рабочего проекта и установите файл, когда другой
сбор или тест этого источника не выполняется:

```bash
cd /путь/к/bakhrushin_tg
sudo install -d -m 700 .browser-state
sudo install -m 600 "$HOME/.browser-state-upload/bolshoi.json" .browser-state/bolshoi.json
```

Команды рассчитаны на текущий Compose с контейнерами от root. При другом
пользователе назначьте файлу владельца, доступного API и worker.

В настройках источника добавьте следующие поля, сохранив остальные параметры:

```json
{
  "fetch_mode": "browser",
  "browser_channel": "chromium",
  "browser_state_name": "bolshoi"
}
```

## 4. Запустить сбор на сервере

Контейнер `celery_worker` должен работать. Из каталога проекта выполните:

```bash
./scripts/collect_bolshoi.sh
```

Скрипт покажет число добавленных материалов. Он собирает новости в БД;
AI-обработка и публикация выполняются отдельными задачами.

При отказе `401/403` обновите cookies и повторите шаги. Даже рабочая локальная
сессия может не дать доступа с серверного IP.

Cookies и JSON-сессию не публикуйте и не добавляйте в Git. После переноса удалите
временный файл заголовка на компьютере и копию из `.browser-state-upload` на
сервере. Рабочий `.browser-state/bolshoi.json` оставьте для сборщика.

Подробности: [перенос cookies на сервер](CHROME_COOKIES_TO_SERVER.md) и
[ручной сбор новостей](MANUAL_BOLSHOI_COLLECTION.md).

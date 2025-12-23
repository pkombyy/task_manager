## Task Manager

Асинхронный сервис управления задачами на FastAPI, RabbitMQ и PostgreSQL.

### Быстрый старт (локально)
- Создайте `.env` из примера и укажите строки подключения.
- Установите зависимости: `pip install -r requirements.txt`
- Запустите инфраструктуру: `docker compose up -d postgres rabbitmq`
- Запустите API: `uvicorn main:app --reload`
- Запустите воркер: `python -m worker.consumer`
- Swagger: `http://localhost:8000/api/v1/docs`

### Запуск через Docker Compose
- `docker compose up --build`
- Поднимутся сервисы: API, worker, PostgreSQL, RabbitMQ (UI на 15672), метрики воркера на :9000.
- Postgres проброшен на хост `localhost:5432` (внутри compose — `postgres:5432`).

### Переменные окружения
См. `env.example`:
- `DATABASE_URL` — строка подключения к Postgres (asyncpg).
- `RABBITMQ_URL` — строка подключения к RabbitMQ.
- `QUEUE_HIGH|MEDIUM|LOW` — названия очередей.
- `METRICS_ENABLED|METRICS_PORT` — включение/порт метрик Prometheus у воркера.
- `WORKER_REQUEUE_ON_FAIL` — возвращать задачу в очередь при ошибке обработки.
- `RETRY_MAX_ATTEMPTS|RETRY_BACKOFF_SECONDS` — сколько ретраев и базовая задержка (экспоненциально).
- `AUTO_STATUS_UPDATES` — включать ли автоматические переходы статусов воркером.

### Алгоритм работы и автопереходы
- API создаёт задачу в БД (status=NEW) и публикует в очередь по приоритету.
- Флаг `AUTO_STATUS_UPDATES` управляет автоматикой:
  - `true`: API сразу ставит PENDING после публикации. Воркер при получении ставит IN_PROGRESS, по завершении — COMPLETED/FAILED, при ошибке может ретраить по настройкам `RETRY_MAX_ATTEMPTS|RETRY_BACKOFF_SECONDS`. CANCELLED ставится через DELETE-эндпоинт.
  - `false`: API не меняет статус (остаётся NEW), воркер статусы не трогает. Обновление статусов выполняет внешняя логика/ручные вызовы API.
- Отмена задачи помечает её CANCELLED; воркер игнорирует завершённые/отменённые.

### Тесты
- `pytest`

### CI
- `.github/workflows/ci.yml` запускает тесты и линтеры на push/PR.


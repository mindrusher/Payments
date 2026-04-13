# Асинхронный сервис процессинга платежей

Микросервис для асинхронной обработки платежей с использованием паттерна Outbox, брокера сообщений RabbitMQ и вебхуков для уведомления клиентов.


## Архитектура

Client → API Gateway (FastAPI) → PostgreSQL (Outbox) → RabbitMQ → Consumer → Webhook


### Компоненты

1. **API сервис** (`api`) - FastAPI приложение для создания и получения платежей
2. **Outbox Worker** (`outbox_worker`) - Сервис для публикации событий из outbox таблицы в RabbitMQ
3. **Consumer** (`consumer`) - Обработчик платежей, эмулирующий работу платежного шлюза
4. **PostgreSQL** - Хранилище платежей и outbox событий
5. **RabbitMQ** - Брокер сообщений с очередями:
   - `payments.new` - основная очередь для новых платежей
   - `payments.dlq` - Dead Letter Queue для необработанных сообщений

### Поток обработки

1. Клиент отправляет POST запрос на создание платежа с `Idempotency-Key`
2. API сохраняет платеж со статусом `pending` и событие в outbox таблицу
3. Outbox worker периодически забирает события и публикует их в RabbitMQ
4. Consumer получает сообщение, эмулирует обработку (2-5 сек, 90% успеха)
5. Consumer обновляет статус платежа и отправляет вебхук клиенту
6. При ошибке вебхука - повторные попытки (3 раза с экспоненциальной задержкой)
7. При 3 неудачных попытках - сообщение отправляется в DLQ

## Технологии

* FastAPI
* SQLAlchemy 2.0
* RabbitMQ
* *FastStream
* PostgreSQL
* Alembic
* Docker
* Docker Compose

## Запуск

### Клонирование репозитория

```bash
git clone https://github.com/mindrusher/Payments.git
cd Payments

# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка всех сервисов
docker-compose down

# Полная очистка (с удалением volumes)
docker-compose down -v

# Создание новой миграции (или после изменений моделей)
docker-compose exec api alembic revision --autogenerate -m "init"

# Запуск миграций в контейнере API
docker-compose exec api alembic upgrade head
```

## Проверка работоспособности
http://localhost:8000/health

## Документация API (SWAGGER)
http://localhost:8000/docs

## Эндпоинты (POST GET)
API-ключ: key

POST /api/v1/payments
GET /api/v1/payments/{payment_id}

## Примеры запросов

```bash
# Создание платежа
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: key" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5000.00,
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {"test": true},
    "webhook_url": "https://example.com/"
  }'

# Получение платежа
curl http://localhost:8000/api/v1/payments/your-payment-id \
  -H "X-API-Key: key"
```

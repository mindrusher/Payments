# import asyncio
# import random
# import logging
# from datetime import datetime
# import uuid

# import httpx
# from faststream.rabbit import RabbitBroker

# from sqlalchemy.ext.asyncio import async_sessionmaker
# from sqlalchemy import select

# from app.core.config import settings
# from app.db.session import engine
# from app.db.models import Payment

# logger = logging.getLogger(__name__)

# broker = RabbitBroker(settings.rabbit_url)

# SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# MAX_RETRIES = 3


# async def send_webhook(webhook_url: str, payment_id: str, status: str):
#     for attempt in range(MAX_RETRIES):
#         try:
#             async with httpx.AsyncClient(timeout=5) as client:
#                 await client.post(
#                     webhook_url,
#                     json={
#                         "payment_id": payment_id,
#                         "status": status,
#                     },
#                 )
#             return True
#         except Exception:
#             await asyncio.sleep(2 ** attempt)

#     return False


# async def send_to_dlq(message: dict):
#     await broker.publish(
#         message=message,
#         queue="payments.dlq",
#     )


# @broker.subscriber("payments.new")
# async def process_payment(message: dict):
#     # asyncio.create_task(handle_payment(message))
#     await handle_payment(message)


# async def handle_payment(message: dict):
#     try:
#         payment_id = message.get("payment_id")

#         if not payment_id or payment_id == "None":
#             logger.error(f"Invalid payment_id in message: {message}")
#             return

#         try:
#             payment_id = uuid.UUID(payment_id_str)
#         except ValueError:
#             logger.error(f"Invalid UUID format: {payment_id_str}")
#             return

#         logger.info(f"Processing payment {payment_id}")

#         async with SessionLocal() as db:
#             result = await db.execute(
#                 select(Payment).where(Payment.id == payment_id)
#             )
#             payment = result.scalar_one_or_none()

#             if not payment:
#                 logger.warning(f"Payment {payment_id} not found")
#                 return

#             if payment.status != "pending":
#                 logger.warning(f"Payment {payment_id} status is {payment.status}, not pending")
#                 return

#         await asyncio.sleep(random.randint(2, 5))

#         success = random.random() < 0.9
#         new_status = "succeeded" if success else "failed"

#         async with SessionLocal() as db:
#             payment = await db.get(Payment, payment_id)

#             if not payment or payment.status != "pending":
#                 return

#             payment.status = new_status
#             payment.processed_at = datetime.utcnow()

#             webhook_url = payment.webhook_url
#             payment_id_str = str(payment.id)

#             await db.commit()

#         webhook_ok = await send_webhook(
#             webhook_url,
#             payment_id_str,
#             new_status,
#         )

#         if not webhook_ok:
#             await send_to_dlq({"payment_id": payment_id_str, "status": new_status})

#     except Exception as e:
#         logger.exception(f"Consumer error: {e}")
#         await send_to_dlq(message)


# async def main():
#     await broker.connect()
#     logger.info("Consumer started")

#     await broker.start()


# if __name__ == "__main__":
#     asyncio.run(main())

import asyncio
from asyncio import Semaphore

import uuid
import random
import logging
from datetime import datetime
from typing import Optional

import httpx
from faststream.rabbit import RabbitBroker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.session import engine
from app.db.models import Payment

logger = logging.getLogger(__name__)

# Создаем брокера с настройками
broker = RabbitBroker(
    settings.rabbit_url
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
MAX_RETRIES = 3

MAX_CONCURRENT = 10  # Не более 10 одновременных обработок
semaphore = Semaphore(MAX_CONCURRENT)


async def send_webhook(webhook_url: str, payment_id: str, status: str) -> bool:
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    webhook_url,
                    json={"payment_id": payment_id, "status": status},
                )
            return True
        except Exception as e:
            logger.warning(f"Webhook attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(2 ** attempt)
    return False


@broker.subscriber("payments.new")
async def process_payment(message: dict):
    """Обработчик сообщений из очереди payments.new"""
    async with semaphore:
        try:
            logger.info(f"Received message: {message}")
            
            payment_id_str = message.get("payment_id")
            if not payment_id_str or payment_id_str == "None":
                logger.error(f"Invalid payment_id in message: {message}")
                return
            
            # Конвертируем в UUID
            try:
                payment_id = uuid.UUID(payment_id_str)
            except ValueError:
                logger.error(f"Invalid UUID format: {payment_id_str}")
                return
            
            logger.info(f"Processing payment {payment_id}")
            
            # Получаем платеж из БД
            async with SessionLocal() as db:
                result = await db.execute(
                    select(Payment).where(Payment.id == payment_id)
                )
                payment = result.scalar_one_or_none()
                
                if not payment:
                    logger.warning(f"Payment {payment_id} not found")
                    return
                
                if payment.status != "pending":
                    logger.info(f"Payment {payment_id} status is {payment.status}, skipping")
                    return
                
                # Имитация обработки
                await asyncio.sleep(random.randint(2, 5))
                
                # 90% успеха
                success = random.random() < 0.9
                new_status = "succeeded" if success else "failed"
                
                # Обновляем статус
                payment.status = new_status
                payment.processed_at = datetime.utcnow()
                webhook_url = payment.webhook_url
                
                await db.commit()
                
                # Отправляем вебхук
                webhook_ok = await send_webhook(webhook_url, str(payment.id), new_status)
                
                if not webhook_ok:
                    logger.error(f"Webhook failed for payment {payment_id}")
                    # Здесь можно отправить в DLQ
                    
                logger.info(f"Payment {payment_id} processed with status {new_status}")
                
        except Exception as e:
            logger.exception(f"Unexpected error processing message: {e}")
            # Не выбрасываем исключение, чтобы не ломать консьюмер


async def main():
    """Запуск consumer"""
    try:
        logger.info("Starting consumer...")
        await broker.connect()
        logger.info("Connected to RabbitMQ")
        
        # Запускаем брокера
        await broker.start()
        logger.info("Consumer is running and waiting for messages")
        
        # Бесконечное ожидание
        await asyncio.Event().wait()
        
    except asyncio.CancelledError:
        logger.info("Consumer was cancelled")
    except KeyboardInterrupt:
        logger.info("Consumer interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in consumer: {e}")
        raise
    finally:
        await broker.close()
        logger.info("Consumer closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Consumer stopped")
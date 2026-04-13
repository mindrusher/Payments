import asyncio
import logging

from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.db.session import engine
from app.services.outbox import get_pending_events
from app.db.models import Outbox

logger = logging.getLogger(__name__)

broker = RabbitBroker(settings.rabbit_url)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

POLL_INTERVAL = 1


async def publish_event(event: Outbox):
    """
    Публикация одного события в RabbitMQ
    """
    logger.info(f"Publishing event {event.id}, topic={event.topic}, payload={event.payload}")
    await broker.publish(
        message=event.payload,
        queue=event.topic,
    )


async def process_outbox():
    """
    Основной цикл обработки outbox
    """
    while True:
        async with SessionLocal() as db:
            events = await get_pending_events(db)

            if not events:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            for event in events:
                try:
                    await publish_event(event)

                    event.status = "sent"

                except Exception as e:
                    logger.error(f"Failed to publish event {event.id}: {e}")

                    event.attempts += 1

                    if event.attempts >= 3:
                        event.status = "failed"

            await db.commit()

        await asyncio.sleep(POLL_INTERVAL)


async def main():
    await broker.connect()
    logger.info("Outbox worker started")

    await process_outbox()


if __name__ == "__main__":
    asyncio.run(main())

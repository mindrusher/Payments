import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Outbox

BATCH_SIZE = 10


async def get_pending_events(db: AsyncSession):
    result = await db.execute(
        select(Outbox)
        .where(Outbox.status == "pending")
        .order_by(Outbox.created_at)
        .limit(BATCH_SIZE)
    )
    return result.scalars().all()
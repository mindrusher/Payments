from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Payment, Outbox
from app.schemas.payment import PaymentCreate

import logging

logger = logging.getLogger(__name__)


async def create_payment(
    db: AsyncSession,
    data: PaymentCreate,
    idempotency_key: str,
) -> Payment:
    """
    Идемпотентное создание платежа с защитой от race
    """

    result = await db.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    payment = Payment(
        amount=data.amount,
        currency=data.currency.value,
        description=data.description,
        meta_info=data.metadata,
        idempotency_key=idempotency_key,
        webhook_url=str(data.webhook_url),
    )

    db.add(payment)
    await db.flush()
    await db.refresh(payment)
    logger.info(f"Created payment with ID: {payment.id}")

    outbox = Outbox(
        topic="payments.new",
        payload={"payment_id": str(payment.id)},
        status="pending",
    )
    db.add(outbox)

    try:
        await db.commit()
        return payment

    except IntegrityError:
        await db.rollback()

        result = await db.execute(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        existing = result.scalar_one()

        return existing

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.payment import (
    PaymentCreate,
    PaymentCreateResponse,
    PaymentResponse,
)
from app.services.payments import create_payment
from app.db.models import Payment
from sqlalchemy import select
from uuid import UUID

router = APIRouter(prefix="/api/v1", tags=["payments"])


@router.post(
    "/payments",
    response_model=PaymentCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_payment_endpoint(
    data: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    if x_api_key != "key":
        raise HTTPException(status_code=403, detail="Forbidden")

    payment = await create_payment(db, data, idempotency_key)

    return PaymentCreateResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    if x_api_key != "key":
        raise HTTPException(status_code=403)

    result = await db.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Not found")

    return payment

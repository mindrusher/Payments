from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict
from enum import Enum


# 🔹 Валюта как Enum (строгое ограничение)
class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


# 🔹 Статусы платежа
class PaymentStatus(str, Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


# 🔹 Base schema с общими настройками
class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,  # важно для SQLAlchemy
        populate_by_name=True,
    )


# 🔹 Создание платежа (request)
class PaymentCreate(BaseSchema):
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: Currency
    description: Optional[str] = Field(None, max_length=255)
    metadata: Optional[Dict[str, Any]] = None
    webhook_url: HttpUrl

    # 💡 Валидация decimal (2 знака после запятой)
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("Amount must have max 2 decimal places")
        return value


# 🔹 Ответ при создании (202)
class PaymentCreateResponse(BaseSchema):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


# 🔹 Полная информация о платеже
class PaymentResponse(BaseSchema):
    id: UUID
    amount: Decimal
    currency: Currency
    description: Optional[str]
    meta_info: Optional[Dict[str, Any]]

    status: PaymentStatus

    webhook_url: HttpUrl

    created_at: datetime
    processed_at: Optional[datetime]
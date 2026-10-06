"""Payment domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class PaymentStatus(str, Enum):
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class PaymentMethod(str, Enum):
    CARD = "CARD"
    UPI = "UPI"
    NETBANKING = "NETBANKING"
    WALLET = "WALLET"


@dataclass
class Money:
    amount_paise: int
    currency: str = "INR"

    def __post_init__(self) -> None:
        if self.amount_paise < 0:
            raise ValueError("amount must be non-negative")
        if len(self.currency) != 3:
            raise ValueError("currency must be ISO-4217")


@dataclass
class PaymentRequest:
    merchant_id: str
    customer_id: str
    money: Money
    method: PaymentMethod
    idempotency_key: str
    return_url: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Payment:
    payment_id: str
    merchant_id: str
    customer_id: str
    amount_paise: int
    currency: str
    method: str
    status: PaymentStatus
    idempotency_key: str
    gateway_ref: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    attempt_count: int = 0

    @staticmethod
    def new(request: PaymentRequest) -> "Payment":
        return Payment(
            payment_id=f"pay_{uuid4().hex[:16]}",
            merchant_id=request.merchant_id,
            customer_id=request.customer_id,
            amount_paise=request.money.amount_paise,
            currency=request.money.currency,
            method=request.method.value,
            status=PaymentStatus.CREATED,
            idempotency_key=request.idempotency_key,
        )


@dataclass
class ConfirmationResult:
    payment_id: str
    status: PaymentStatus
    latency_ms: int
    pool_wait_ms: int
    timed_out: bool
    message: str

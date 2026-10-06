"""Payment application service — authorize, capture, confirm."""

from __future__ import annotations

import logging
import time
from typing import Optional

from services.payment.models import (
    ConfirmationResult,
    Payment,
    PaymentRequest,
    PaymentStatus,
)
from services.payment.repository import DB_ENGINE, DB_POOL_SIZE, PoolExhausted, REPO

logger = logging.getLogger("nexapay.payment.service")

CONFIRMATION_TIMEOUT_MS = 8700
MAX_CONFIRM_ATTEMPTS = 3
BACKOFF_BASE_MS = 200


class RedisLock:
    def __init__(self) -> None:
        self._held: set[str] = set()

    def acquire(self, key: str) -> bool:
        token = f"lock:payment:{key}"
        if token in self._held:
            return False
        self._held.add(token)
        return True

    def release(self, key: str) -> None:
        self._held.discard(f"lock:payment:{key}")


REDIS = RedisLock()


class KafkaPublisher:
    def publish(self, topic: str, payload: dict) -> None:
        logger.info("kafka publish topic=%s payment_id=%s", topic, payload.get("payment_id"))


KAFKA = KafkaPublisher()


class PaymentService:
    def create(self, request: PaymentRequest) -> Payment:
        existing = REPO.get_by_idempotency(request.idempotency_key)
        if existing:
            return existing
        payment = Payment.new(request)
        REPO.insert(payment)
        KAFKA.publish("payments.created", {"payment_id": payment.payment_id})
        return payment

    def authorize(self, payment_id: str) -> Payment:
        self._require(payment_id)
        return REPO.update_status(payment_id, PaymentStatus.AUTHORIZED)

    def capture(self, payment_id: str) -> Payment:
        payment = self._require(payment_id)
        if payment.status != PaymentStatus.AUTHORIZED:
            raise ValueError("capture requires AUTHORIZED payment")
        return REPO.update_status(payment_id, PaymentStatus.CAPTURED)

    def confirm(self, payment_id: str) -> ConfirmationResult:
        started = time.time()
        payment = self._require(payment_id)
        if not REDIS.acquire(payment_id):
            return ConfirmationResult(
                payment_id=payment_id,
                status=payment.status,
                latency_ms=int((time.time() - started) * 1000),
                pool_wait_ms=0,
                timed_out=False,
                message="confirmation already in progress",
            )
        try:
            return self._confirm_with_retry(payment, started)
        finally:
            REDIS.release(payment_id)

    def _confirm_with_retry(self, payment: Payment, started: float) -> ConfirmationResult:
        last_error: Optional[str] = None
        pool_wait_ms = 0
        for attempt in range(1, MAX_CONFIRM_ATTEMPTS + 1):
            payment.attempt_count = attempt
            try:
                attempt_start = time.time()
                REPO.update_status(payment.payment_id, PaymentStatus.CONFIRMED)
                elapsed_ms = int((time.time() - started) * 1000)
                pool_wait_ms += int((time.time() - attempt_start) * 1000)
                if elapsed_ms > CONFIRMATION_TIMEOUT_MS:
                    REPO.update_status(
                        payment.payment_id, PaymentStatus.TIMED_OUT, "confirmation_timeout"
                    )
                    return ConfirmationResult(
                        payment_id=payment.payment_id,
                        status=PaymentStatus.TIMED_OUT,
                        latency_ms=elapsed_ms,
                        pool_wait_ms=pool_wait_ms,
                        timed_out=True,
                        message="Payment confirmation timeout",
                    )
                KAFKA.publish(
                    "payments.confirmed",
                    {
                        "payment_id": payment.payment_id,
                        "engine": DB_ENGINE,
                        "pool": DB_POOL_SIZE,
                    },
                )
                return ConfirmationResult(
                    payment_id=payment.payment_id,
                    status=PaymentStatus.CONFIRMED,
                    latency_ms=elapsed_ms,
                    pool_wait_ms=pool_wait_ms,
                    timed_out=False,
                    message="confirmed",
                )
            except PoolExhausted as exc:
                last_error = str(exc)
                backoff = BACKOFF_BASE_MS * (2 ** (attempt - 1))
                logger.error(
                    "confirm pool exhausted payment=%s attempt=%s backoff_ms=%s",
                    payment.payment_id,
                    attempt,
                    backoff,
                )
                time.sleep(backoff / 1000)
        REPO.update_status(payment.payment_id, PaymentStatus.TIMED_OUT, last_error)
        return ConfirmationResult(
            payment_id=payment.payment_id,
            status=PaymentStatus.TIMED_OUT,
            latency_ms=int((time.time() - started) * 1000),
            pool_wait_ms=pool_wait_ms,
            timed_out=True,
            message="Payment confirmation timeout",
        )

    def _require(self, payment_id: str) -> Payment:
        payment = REPO.get(payment_id)
        if not payment:
            raise KeyError(f"unknown payment {payment_id}")
        return payment


PAYMENT_SERVICE = PaymentService()

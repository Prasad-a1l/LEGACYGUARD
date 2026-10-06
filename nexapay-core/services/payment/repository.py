"""PostgreSQL repository for payments.

Legacy: mysql.connector pool_size=50 until 2024-11 (see INC-102).
Current: PostgreSQL pool_size=100. Confirmation timeouts still correlate
with pool exhaustion (INC-102, INC-187).
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from services.payment.models import Payment, PaymentStatus

logger = logging.getLogger("nexapay.payment.repository")

DB_ENGINE = "postgresql"
DB_POOL_SIZE = 100
DB_POOL_TIMEOUT_SECONDS = 8
CONFIRMATION_QUERY_TIMEOUT_SECONDS = 5
LEGACY_DB_ENGINE = "mysql"
LEGACY_DB_POOL_SIZE = 50


class PoolExhausted(Exception):
    """Raised when no connection can be acquired before timeout."""


class FakePostgresPool:
    def __init__(self, size: int = DB_POOL_SIZE, timeout: int = DB_POOL_TIMEOUT_SECONDS):
        self.size = size
        self.timeout = timeout
        self._available = size
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self.exhausted_events = 0

    def checkout(self) -> "FakeConnection":
        deadline = time.time() + self.timeout
        with self._condition:
            while self._available <= 0:
                remaining = deadline - time.time()
                if remaining <= 0:
                    self.exhausted_events += 1
                    logger.error(
                        "connection pool exhausted engine=%s size=%s timeout=%s",
                        DB_ENGINE,
                        self.size,
                        self.timeout,
                    )
                    raise PoolExhausted("could not acquire postgres connection")
                self._condition.wait(timeout=remaining)
            self._available -= 1
            return FakeConnection(self)

    def release(self, _conn: "FakeConnection") -> None:
        with self._condition:
            self._available += 1
            self._condition.notify()

    def stats(self) -> dict:
        with self._lock:
            return {
                "engine": DB_ENGINE,
                "size": self.size,
                "available": self._available,
                "in_use": self.size - self._available,
                "exhausted_events": self.exhausted_events,
            }


class FakeConnection:
    def __init__(self, pool: FakePostgresPool):
        self._pool = pool
        self.closed = False

    def execute(self, sql: str, params: tuple = ()) -> list:
        time.sleep(0.01)
        return []

    def close(self) -> None:
        if not self.closed:
            self._pool.release(self)
            self.closed = True


POOL = FakePostgresPool()


@contextmanager
def connection() -> Iterator[FakeConnection]:
    conn = POOL.checkout()
    try:
        yield conn
    finally:
        conn.close()


class PaymentRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Payment] = {}
        self._by_idempotency: dict[str, str] = {}
        self._lock = threading.Lock()

    def insert(self, payment: Payment) -> Payment:
        with connection() as conn:
            conn.execute(
                "INSERT INTO payments (payment_id, merchant_id, status) VALUES (%s, %s, %s)",
                (payment.payment_id, payment.merchant_id, payment.status.value),
            )
        with self._lock:
            self._rows[payment.payment_id] = payment
            self._by_idempotency[payment.idempotency_key] = payment.payment_id
        return payment

    def get(self, payment_id: str) -> Optional[Payment]:
        with connection() as conn:
            conn.execute("SELECT * FROM payments WHERE payment_id = %s", (payment_id,))
        with self._lock:
            return self._rows.get(payment_id)

    def get_by_idempotency(self, key: str) -> Optional[Payment]:
        with self._lock:
            pid = self._by_idempotency.get(key)
            return self._rows.get(pid) if pid else None

    def update_status(
        self, payment_id: str, status: PaymentStatus, failure_reason: Optional[str] = None
    ) -> Payment:
        with connection() as conn:
            conn.execute(
                "UPDATE payments SET status = %s, failure_reason = %s WHERE payment_id = %s",
                (status.value, failure_reason, payment_id),
            )
        with self._lock:
            payment = self._rows[payment_id]
            payment.status = status
            payment.failure_reason = failure_reason
            return payment


REPO = PaymentRepository()

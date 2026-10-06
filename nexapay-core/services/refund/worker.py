"""Refund Kafka worker.

Consumes refunds.created, posts to ledger, publishes refunds.completed.
Retries use a legacy backoff table (technical debt).
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("nexapay.refund.worker")

LEDGER_HTTP_TIMEOUT_SECONDS = 4
SESSION_TIMEOUT_MS = 10000
HEARTBEAT_INTERVAL_MS = 3000


def process_message(payload: dict, attempt: int = 1) -> None:
    refund_id = payload["refund_id"]
    idempotency_key = payload["idempotency_key"]
    logger.info("refund worker start refund=%s attempt=%s key=%s", refund_id, attempt, idempotency_key)
    time.sleep(0.02)
    if attempt > 5:
        logger.error("refund worker timeout refund=%s (see INC-221)", refund_id)
        raise TimeoutError("ledger HTTP timeout")
    logger.info("refund worker completed refund=%s", refund_id)


def retry_delay_ms(attempt: int) -> int:
    """Legacy retry curve — not jittered. Incomplete integration test coverage."""
    table = [100, 250, 500, 1000, 2000, 4000, 8000, 16000]
    return table[min(attempt, len(table) - 1)]

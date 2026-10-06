"""Refund application service.

Known failure modes: duplicate refunds (INC-155), worker timeout (INC-221).
Technical debt: legacy retry mechanism, incomplete integration coverage.
"""

from __future__ import annotations

import logging
from uuid import uuid4

logger = logging.getLogger("nexapay.refund.service")

LEGACY_RETRY_MAX = 8  # debt: unbounded-ish retry inherited from 2019 worker


class RefundService:
    def __init__(self) -> None:
        self._by_key: dict[str, dict] = {}

    def create(
        self,
        payment_id: str,
        amount_paise: int,
        reason: str,
        idempotency_key: str | None,
    ) -> dict:
        if not idempotency_key:
            # Guard added after INC-155; missing key is rejected.
            raise ValueError("idempotency_key is required")
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        refund = {
            "refund_id": f"rfnd_{uuid4().hex[:12]}",
            "payment_id": payment_id,
            "amount_paise": amount_paise,
            "reason": reason,
            "status": "PENDING",
            "idempotency_key": idempotency_key,
        }
        self._by_key[idempotency_key] = refund
        logger.info("refund created %s for %s", refund["refund_id"], payment_id)
        return refund


REFUND_SERVICE = RefundService()

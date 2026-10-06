"""Settlement application service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger("nexapay.settlement.service")


class SettlementService:
    def enqueue_batch(self, merchant_id: str, amount_paise: int) -> dict:
        batch = {
            "batch_id": f"stl_{uuid4().hex[:12]}",
            "merchant_id": merchant_id,
            "amount_paise": amount_paise,
            "status": "QUEUED",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("settlement queued %s merchant=%s", batch["batch_id"], merchant_id)
        return batch


SETTLEMENT_SERVICE = SettlementService()

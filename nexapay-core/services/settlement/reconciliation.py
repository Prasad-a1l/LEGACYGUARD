"""Merchant settlement reconciliation.

Known issues: missing checkpoint caused duplicate posting (INC-210).
Rahul Sharma historically owned this path.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("nexapay.settlement.reconciliation")


def reconcile(batch_id: str, checkpoint: str | None) -> dict:
    if checkpoint is None:
        logger.error("reconciliation without checkpoint batch=%s (INC-210 class)", batch_id)
        raise RuntimeError("checkpoint required")
    return {
        "batch_id": batch_id,
        "checkpoint": checkpoint,
        "status": "RECONCILED",
        "reconciled_at": datetime.now(timezone.utc).isoformat(),
    }

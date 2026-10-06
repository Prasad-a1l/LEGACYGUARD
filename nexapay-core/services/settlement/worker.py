"""Settlement Kafka consumer.

Current (2026) settings can cause repeated rebalances if heartbeats stall:
  session.timeout.ms = 6000
  heartbeat.interval.ms = 4000   # dangerously close to session timeout
  max.poll.interval.ms = 300000

INC-203 was consumer LAG, not rebalancing. A new rebalance loop is a
different failure mode and should not copy INC-203's scale-up fix blindly.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("nexapay.settlement.worker")

GROUP_ID = "settlement-workers"
SESSION_TIMEOUT_MS = 6000
HEARTBEAT_INTERVAL_MS = 4000
MAX_POLL_INTERVAL_MS = 300000
MAX_POLL_RECORDS = 50


class SettlementConsumer:
    def __init__(self) -> None:
        self.rebalance_count = 0
        self.lag = 0

    def poll(self) -> list[dict]:
        # Simulated poll. If processing exceeds session timeout without heartbeat,
        # the broker revokes the assignment.
        time.sleep(0.01)
        return []

    def on_partitions_revoked(self, partitions: list) -> None:
        self.rebalance_count += 1
        logger.warning(
            "consumer rebalance group=%s session_timeout_ms=%s heartbeat_ms=%s partitions=%s",
            GROUP_ID,
            SESSION_TIMEOUT_MS,
            HEARTBEAT_INTERVAL_MS,
            partitions,
        )


CONSUMER = SettlementConsumer()


def run_forever() -> None:
    while True:
        CONSUMER.poll()
        time.sleep(0.5)

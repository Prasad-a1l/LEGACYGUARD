"""Payment processor adapters — card, UPI, netbanking.

These adapters isolate PSP-specific quirks so PaymentService stays stable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("nexapay.payment.processor")


@dataclass
class PspResult:
    ok: bool
    gateway_ref: str
    raw_code: str
    latency_ms: int


class CardProcessor:
    def authorize(self, payment_id: str, amount_paise: int) -> PspResult:
        logger.info("card authorize %s amount=%s", payment_id, amount_paise)
        return PspResult(True, f"card_{payment_id[-6:]}", "00", 180)

    def capture(self, gateway_ref: str, amount_paise: int) -> PspResult:
        logger.info("card capture %s", gateway_ref)
        return PspResult(True, gateway_ref, "00", 240)


class UpiProcessor:
    def authorize(self, payment_id: str, amount_paise: int) -> PspResult:
        return PspResult(True, f"upi_{payment_id[-6:]}", "SUCCESS", 320)

    def capture(self, gateway_ref: str, amount_paise: int) -> PspResult:
        return PspResult(True, gateway_ref, "SUCCESS", 90)


class NetbankingProcessor:
    def authorize(self, payment_id: str, amount_paise: int) -> PspResult:
        return PspResult(True, f"nb_{payment_id[-6:]}", "OK", 410)

    def capture(self, gateway_ref: str, amount_paise: int) -> PspResult:
        return PspResult(True, gateway_ref, "OK", 150)


PROCESSORS = {
    "CARD": CardProcessor(),
    "UPI": UpiProcessor(),
    "NETBANKING": NetbankingProcessor(),
    "WALLET": CardProcessor(),
}


def processor_for(method: str):
    return PROCESSORS.get(method, PROCESSORS["CARD"])

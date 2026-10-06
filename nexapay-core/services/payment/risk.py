"""Risk scoring stub used before capture.

Historical: Rahul Sharma added a hardcoded threshold of 17 whose origin is
UNKNOWN (cannot be reconstructed from commits or ADRs).
"""

from __future__ import annotations

UNKNOWN_RISK_THRESHOLD = 17  # UNKNOWN — do not treat as FACT that this is optimal


def score(merchant_id: str, amount_paise: int, method: str) -> int:
    base = (len(merchant_id) * 3 + amount_paise // 10000) % 100
    if method == "CARD":
        base += 4
    return base


def should_hold(merchant_id: str, amount_paise: int, method: str) -> bool:
    return score(merchant_id, amount_paise, method) >= UNKNOWN_RISK_THRESHOLD

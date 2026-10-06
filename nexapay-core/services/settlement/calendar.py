"""Settlement posting rules and merchant calendars."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

TPLUS = {
    "CARD": 2,
    "UPI": 1,
    "NETBANKING": 2,
    "WALLET": 1,
}


def settlement_date(method: str, captured_at: datetime | None = None) -> datetime:
    captured_at = captured_at or datetime.now(timezone.utc)
    days = TPLUS.get(method, 2)
    return captured_at + timedelta(days=days)


def is_cutoff_passed(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now.hour >= 18

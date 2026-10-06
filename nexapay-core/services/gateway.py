"""API Gateway timeout alignment (see INC-176)."""

GATEWAY_CAPTURE_TIMEOUT_MS = 5000
GATEWAY_CONFIRM_TIMEOUT_MS = 9000
RATE_LIMIT_RPS = 400


def route_service(path: str) -> str:
    if path.startswith("/payments/v2/refund") or path.startswith("/payments/v2") and "refund" in path:
        return "RefundService"
    if path.startswith("/payments"):
        return "PaymentService"
    if path.startswith("/settlements"):
        return "SettlementService"
    return "unknown"

"""HTTP controllers for PaymentService.

Public contract as implemented in code (2026):
  POST /payments/v2
  POST /payments/v2/{payment_id}/confirm
"""

from __future__ import annotations

from flask import Flask, jsonify, request

from services.payment.models import Money, PaymentMethod, PaymentRequest
from services.payment.service import PAYMENT_SERVICE

# FACT: these path constants are the implemented HTTP contract.
PAYMENTS_CREATE_PATH = "/payments/v2"
PAYMENTS_CONFIRM_PATH = "/payments/v2/<payment_id>/confirm"
PAYMENTS_CAPTURE_PATH = "/payments/v2/<payment_id>/capture"

app = Flask(__name__)


@app.post("/payments/v2")
def create_payment():
    body = request.get_json(force=True)
    req = PaymentRequest(
        merchant_id=body["merchant_id"],
        customer_id=body["customer_id"],
        money=Money(int(body["amount_paise"]), body.get("currency", "INR")),
        method=PaymentMethod(body.get("method", "CARD")),
        idempotency_key=request.headers.get("Idempotency-Key") or body["idempotency_key"],
        return_url=body.get("return_url"),
        metadata=body.get("metadata") or {},
    )
    payment = PAYMENT_SERVICE.create(req)
    return jsonify(
        {
            "payment_id": payment.payment_id,
            "status": payment.status.value,
            "path": PAYMENTS_CREATE_PATH,
        }
    ), 201


@app.post("/payments/v2/<payment_id>/confirm")
def confirm_payment(payment_id: str):
    result = PAYMENT_SERVICE.confirm(payment_id)
    status_code = 504 if result.timed_out else 200
    return jsonify(
        {
            "payment_id": result.payment_id,
            "status": result.status.value,
            "latency_ms": result.latency_ms,
            "message": result.message,
        }
    ), status_code


@app.post("/payments/v2/<payment_id>/capture")
def capture_payment(payment_id: str):
    payment = PAYMENT_SERVICE.capture(payment_id)
    return jsonify({"payment_id": payment.payment_id, "status": payment.status.value})

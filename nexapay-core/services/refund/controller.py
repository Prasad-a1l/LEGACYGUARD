"""Refund HTTP API.

CODE CONTRACT (authoritative for runtime):
  POST /payments/v2/refund

This intentionally disagrees with OpenAPI and the developer guide so the
governance gate can demonstrate contradiction detection.
"""

from __future__ import annotations

from flask import Flask, jsonify, request

from services.refund.service import REFUND_SERVICE

REFUND_CREATE_PATH = "/payments/v2/refund"

app = Flask(__name__)


@app.post("/payments/v2/refund")
def create_refund():
    body = request.get_json(force=True)
    refund = REFUND_SERVICE.create(
        payment_id=body["payment_id"],
        amount_paise=int(body["amount_paise"]),
        reason=body.get("reason", "customer_request"),
        idempotency_key=request.headers.get("Idempotency-Key") or body.get("idempotency_key"),
    )
    return jsonify(refund), 202

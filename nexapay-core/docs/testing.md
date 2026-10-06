# Test strategy (excerpt)

Unit: payment idempotency, refund idempotency, settlement checkpoints.
Integration gaps: refund retry storms, Kafka rebalance under heartbeat miss,
confirmation under pool saturation.

Traceability:
- REQ-023 Refund SLA → RefundService → TC-087
- REQ-011 Confirmation budget → PaymentService.confirm

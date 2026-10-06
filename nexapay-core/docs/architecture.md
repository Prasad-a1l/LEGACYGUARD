# Architecture — NexaPay Core (2026)

Services: PaymentService, RefundService, SettlementService.
Datastore: PostgreSQL (migrated from MySQL in 2025).
Cache: Redis. Broker: Kafka. Edge: API Gateway.

Payment confirmation uses a connection pool of 100. Historical MySQL pool was 50.

## APIs (intended public)

- POST /payments/v2
- POST /payments/v2/{id}/confirm

Refund documentation is split across OpenAPI and the developer guide and must be reconciled.

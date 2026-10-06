-- NexaPay Core schema (PostgreSQL, 2026)
-- Historical: MySQL 5.7 through 2024

CREATE TABLE payments (
    payment_id        TEXT PRIMARY KEY,
    merchant_id       TEXT NOT NULL,
    customer_id       TEXT NOT NULL,
    amount_paise      BIGINT NOT NULL,
    currency          CHAR(3) NOT NULL DEFAULT 'INR',
    method            TEXT NOT NULL,
    status            TEXT NOT NULL,
    idempotency_key   TEXT UNIQUE NOT NULL,
    gateway_ref       TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at      TIMESTAMPTZ,
    failure_reason    TEXT,
    attempt_count     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_payments_merchant ON payments (merchant_id);
CREATE INDEX idx_payments_status ON payments (status);

CREATE TABLE refunds (
    refund_id         TEXT PRIMARY KEY,
    payment_id        TEXT NOT NULL REFERENCES payments (payment_id),
    amount_paise      BIGINT NOT NULL,
    reason            TEXT,
    status            TEXT NOT NULL,
    idempotency_key   TEXT UNIQUE NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE settlement_batches (
    batch_id          TEXT PRIMARY KEY,
    merchant_id       TEXT NOT NULL,
    amount_paise      BIGINT NOT NULL,
    status            TEXT NOT NULL,
    checkpoint        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE settlement_entries (
    entry_id          TEXT PRIMARY KEY,
    batch_id          TEXT NOT NULL REFERENCES settlement_batches (batch_id),
    merchant_id       TEXT NOT NULL,
    amount_paise      BIGINT NOT NULL
);

CREATE INDEX idx_settlement_entries_merchant ON settlement_entries (merchant_id);

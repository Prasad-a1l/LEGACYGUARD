-- 2025-03: MySQL → PostgreSQL persistence migration (ADR-018)
ALTER TABLE payments ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0;

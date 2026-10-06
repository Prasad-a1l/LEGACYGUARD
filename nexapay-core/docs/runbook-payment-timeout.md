# Runbook — Payment confirmation timeouts

Symptoms:
- Confirmations sit in PENDING
- Latency > 8.7s
- Pool waiters increase on PostgreSQL

Do not copy the 2024 MySQL pool=50 change. Current engine is PostgreSQL, pool=100.

Related: INC-102, INC-187.
Owner historically: Rahul Sharma (former). Secondary: Priya Nair.

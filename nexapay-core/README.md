# NexaPay Core

Nine-year-old payment processing platform for **NEXAPAY**.

```
                    API Gateway
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
        Payment       Refund      Settlement
        Service       Service       Service
             │           │           │
             └───────────┼───────────┘
                         ▼
                    PostgreSQL
                         │
                    ┌────┴────┐
                    ▼         ▼
                  Redis      Kafka
```

Until 2024, Payment persistence was MySQL with `pool_size=50`.
2025 migration: PostgreSQL, `pool_size=100`.

Primary historical owner of Payment + Settlement: **Rahul Sharma** (former employee).

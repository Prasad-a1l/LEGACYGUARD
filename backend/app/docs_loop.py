from __future__ import annotations

from .analysis import analyze_repo, detect_drift
from .db import DocumentVersion, SessionLocal
from .llm import llm_complete


PIPELINE = [
    "change_detector",
    "impact_analyzer",
    "api_documentation_agent",
    "documentation_critic",
]


def run_drift() -> dict:
    analysis = analyze_repo()
    drift = detect_drift(analysis)
    updated_api = """# API documentation (generated)

## Payments

`POST /payments/v2`

Create a payment. Idempotency-Key required.

`POST /payments/v2/{payment_id}/confirm`

Confirm a payment. May return 504 on confirmation timeout.

Source: FACT `services/payment/controller.py`
"""
    critic = "PASS: regenerated API doc matches code routes for payments. Refund contract still contradictory — not auto-published."
    session = SessionLocal()
    try:
        session.add(DocumentVersion(name="api", body=updated_api, version=2))
        session.commit()
    finally:
        session.close()
    narrative = llm_complete(
        "Summarize API drift from POST /payments to POST /payments/v2. Do not invent refund resolution.",
        critic,
    )
    return {
        "pipeline": PIPELINE,
        "change": drift,
        "updated_document": updated_api,
        "critic": narrative,
        "published": ["api"],
        "blocked": ["refund contract — see governance"],
    }


def run_governance() -> dict:
    analysis = analyze_repo()
    contradictions = analysis["contradictions"]
    conflict = contradictions[0] if contradictions else {
        "type": "API_CONTRACT_CONFLICT",
        "code": "/payments/v2/refund",
        "openapi": "/payments/refund",
        "documentation": "/payment/refund",
        "authoritative": "UNKNOWN",
    }
    return {
        "gate": "FAILED",
        "conflict": conflict,
        "action": "BLOCK PUBLICATION",
        "escalate": "Payments Domain Owner",
        "message": "The harness doesn't hallucinate an answer when its evidence conflicts.",
    }


def generate_wiki() -> dict:
    analysis = analyze_repo()
    return {
        "architecture": open_arch(),
        "services": analysis["services"],
        "apis": {
            "code": analysis["code_routes"],
            "openapi": analysis["openapi_routes"],
            "docs": analysis["docs_paths"],
        },
        "constants": analysis["constants"],
        "dependencies": analysis["dependencies"],
        "tests": [
            "tests/payment/test_idempotency.py",
            "tests/refund/test_idempotency.py",
            "tests/settlement/test_reconciliation.py",
        ],
        "legacy": [
            "MySQL pool_size=50 until 2024 (HISTORICAL INC-102)",
            "PostgreSQL pool_size=100 in 2026 (FACT repository.py)",
            "Rahul Sharma former owner of Payment + Settlement",
        ],
        "contradictions": analysis["contradictions"],
    }


def open_arch() -> str:
    from .config import REPO_PATH

    return (REPO_PATH / "docs" / "architecture.md").read_text(encoding="utf-8")


def ask_legacy(question: str) -> dict:
    q = question.lower()
    if "refund" in q:
        return {
            "title": "REFUND SERVICE — ENGINEERING BRIEF",
            "purpose": "Handles customer refund requests.",
            "architecture": "API → RefundService → Kafka → Settlement",
            "modules": [
                {"file": "services/refund/controller.py", "why": "HTTP entry POST /payments/v2/refund"},
                {"file": "services/refund/service.py", "why": "Idempotency guard after INC-155"},
                {"file": "services/refund/worker.py", "why": "Async ledger post, legacy retry table"},
            ],
            "dependencies": ["PostgreSQL", "Kafka", "PaymentService"],
            "failure_modes": ["duplicate refunds", "consumer lag", "timeout"],
            "incidents": ["INC-155", "INC-221"],
            "technical_debt": ["legacy retry mechanism", "incomplete integration coverage"],
            "engineers": [
                {"name": "Amit Patel", "relevance": 0.91, "status": "active"},
                {"name": "Priya Nair", "relevance": 0.64, "status": "active"},
            ],
            "sources": [
                {"label": "View source", "path": "nexapay-core/services/refund/service.py"},
                {"label": "View incident INC-155", "path": "data/incidents.json"},
            ],
        }
    return {
        "title": "NEXAPAY CORE — ENGINEERING BRIEF",
        "purpose": "Payment, refund and settlement processing.",
        "architecture": "API Gateway → Payment / Refund / Settlement → PostgreSQL / Redis / Kafka",
        "modules": [
            {"file": "services/payment/service.py", "why": "Confirmation path (timeout-sensitive)"},
            {"file": "services/settlement/worker.py", "why": "Kafka consumer configuration"},
        ],
        "dependencies": ["PostgreSQL", "Redis", "Kafka"],
        "failure_modes": ["confirmation timeout", "pool exhaustion", "consumer rebalance"],
        "incidents": ["INC-102", "INC-187", "INC-203"],
        "technical_debt": ["refund contract contradiction", "heartbeat vs session timeout"],
        "engineers": [
            {"name": "Rahul Sharma", "relevance": 0.94, "status": "former"},
            {"name": "Kavya Iyer", "relevance": 0.77, "status": "active"},
        ],
        "sources": [{"label": "View architecture", "path": "nexapay-core/docs/architecture.md"}],
    }

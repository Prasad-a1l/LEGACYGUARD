"""Quick harness smoke test for demo scenarios."""

from __future__ import annotations

import json
import sys
import time

from app.db import init_db
from app.harness import HUB, apply_decision, resolve_run, start_run
from app.kg import KnowledgeGraph
from app.rag import VectorIndex
from app.seed import seed


def wait(run_id: str, timeout: float = 25) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = HUB.get(run_id)
        status = last.get("status")
        if status in {"awaiting_approval", "escalated", "error"}:
            return last
        time.sleep(0.2)
    return last


def main() -> int:
    init_db()
    from app.db import Incident, SessionLocal

    session = SessionLocal()
    try:
        has = session.query(Incident).count()
    finally:
        session.close()
    if has < 8:
        seed()
    else:
        VectorIndex.instance().rebuild()
        KnowledgeGraph.instance().rebuild()

    rid = start_run("Payment confirmations are timing out intermittently.", "known_timeout")
    s = wait(rid)
    matches = [(m.get("id"), m.get("similarity_pct")) for m in s.get("historical_matches") or []]
    print("KNOWN", s.get("status"), s.get("evidence_path"), matches, s.get("gate"), s.get("error"))
    if s.get("status") == "error":
        print(s.get("error"))
        return 1
    if s.get("evidence_path") != "internal":
        print("expected internal path")
        return 1

    rid2 = start_run(
        "Kafka consumers are repeatedly rebalancing and settlement processing is delayed.",
        "unknown_kafka",
    )
    s2 = wait(rid2, timeout=30)
    print(
        "UNKNOWN",
        s2.get("status"),
        s2.get("evidence_path"),
        [(m.get("id"), m.get("similarity_pct")) for m in s2.get("historical_matches") or []],
        bool(s2.get("external_evidence")),
        s2.get("error"),
    )
    if s2.get("evidence_path") != "external":
        print("expected external fallback")
        return 1

    apply_decision(rid, "approve")
    out = resolve_run(rid, "Connection pool exhaustion", "Pool size increased 50 → 100 on PostgreSQL.", "Incident resolved.")
    print("CLOSED_LOOP", out.get("incident_id"))
    print(json.dumps({"ok": True}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

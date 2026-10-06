from __future__ import annotations

import json
from pathlib import Path

from .config import DATA_DIR, REPO_PATH
from .db import (
    AuditLog,
    DocumentVersion,
    Employee,
    HarnessRun,
    Incident,
    KnowledgeItem,
    SessionLocal,
    Solution,
    init_db,
)
from .kg import KnowledgeGraph
from .rag import VectorIndex


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def seed() -> dict:
    init_db()
    session = SessionLocal()
    try:
        session.query(AuditLog).delete()
        session.query(HarnessRun).delete()
        session.query(DocumentVersion).delete()
        session.query(KnowledgeItem).delete()
        session.query(Solution).delete()
        session.query(Incident).delete()
        session.query(Employee).delete()

        company = _load("employees.json")
        for emp in company["employees"]:
            session.add(
                Employee(
                    id=emp["id"],
                    name=emp["name"],
                    title=emp["title"],
                    status=emp["status"],
                    team=emp["team"],
                    payload_json=json.dumps(emp),
                )
            )

        incidents = _load("incidents.json")
        for inc in incidents:
            session.add(
                Incident(
                    id=inc["id"],
                    service=inc["service"],
                    title=inc["title"],
                    failure=inc["failure"],
                    root_cause=inc["root_cause"],
                    resolution=inc["resolution"],
                    status=inc["status"],
                    verified=inc["verified"],
                    severity=inc["severity"],
                    year=inc["year"],
                    date=inc["date"],
                    resolved_by=inc["resolved_by"],
                    payload_json=json.dumps(inc),
                )
            )
            session.add(
                Solution(
                    id=f"SOL-{inc['id']}",
                    incident_id=inc["id"],
                    body=inc["resolution"],
                    verified=True,
                )
            )
            session.add(
                KnowledgeItem(
                    id=f"KI-{inc['id']}",
                    kind="incident",
                    title=inc["title"],
                    body=inc["summary"],
                    source_type="HISTORICAL",
                    verified=True,
                )
            )

        for pm in _load("postmortems.json"):
            session.add(
                KnowledgeItem(
                    id=pm["id"],
                    kind="postmortem",
                    title=pm["title"],
                    body=pm["body"],
                    source_type="HISTORICAL",
                    verified=True,
                )
            )

        arch_md = (REPO_PATH / "docs" / "architecture.md").read_text(encoding="utf-8")
        session.add(
            DocumentVersion(name="architecture", body=arch_md, version=1)
        )
        session.add(
            DocumentVersion(
                name="api",
                body=(REPO_PATH / "api" / "openapi.yaml").read_text(encoding="utf-8"),
                version=1,
            )
        )
        session.commit()
    finally:
        session.close()

    index = VectorIndex.instance()
    index.rebuild()
    graph = KnowledgeGraph.instance()
    graph.rebuild()
    return {"ok": True, "incidents": 10, "employees": 8, "repo": str(REPO_PATH)}


if __name__ == "__main__":
    print(seed())

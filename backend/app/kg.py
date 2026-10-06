from __future__ import annotations

import json
from typing import Any

import networkx as nx

from .analysis import analyze_repo
from .db import Employee, Incident, SessionLocal


class KnowledgeGraph:
    _instance: "KnowledgeGraph | None" = None

    def __init__(self) -> None:
        self.g = nx.DiGraph()

    @classmethod
    def instance(cls) -> "KnowledgeGraph":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def rebuild(self) -> None:
        self.g = nx.DiGraph()
        analysis = analyze_repo()
        session = SessionLocal()
        try:
            employees = session.query(Employee).all()
            incidents = session.query(Incident).all()
        finally:
            session.close()

        for svc in analysis["services"]:
            self.g.add_node(svc["name"], kind="module", label=f"{svc['name']}Service")
        for dep in analysis["dependencies"]:
            self.g.add_node(dep, kind="dependency", label=dep)
            for svc in analysis["services"]:
                self.g.add_edge(svc["name"], dep, rel="depends_on")

        for route in analysis["code_routes"]:
            nid = f"API {route['path']}"
            self.g.add_node(nid, kind="api", label=nid)
            self.g.add_edge(route["service"], nid, rel="exposes")

        self.g.add_node("REQ-023", kind="requirement", label="REQ-023 Refund SLA")
        self.g.add_edge("REQ-023", "Refund", rel="implemented_by")
        self.g.add_node("TC-087", kind="test", label="TC-087 refund idempotency")
        self.g.add_edge("Refund", "TC-087", rel="tested_by")
        self.g.add_node("refund.md", kind="document", label="docs/developer-guide-refunds.md")
        self.g.add_edge("Refund", "refund.md", rel="documented_by")

        emp_payloads = []
        for emp in employees:
            payload = json.loads(emp.payload_json)
            emp_payloads.append(payload)
            self.g.add_node(emp.id, kind="engineer", label=emp.name, status=emp.status, title=emp.title)
            for mod in payload.get("modules", []):
                if not self.g.has_node(mod):
                    self.g.add_node(mod, kind="module", label=mod)
                self.g.add_edge(emp.id, mod, rel="owns")

        for inc in incidents:
            payload = json.loads(inc.payload_json)
            self.g.add_node(inc.id, kind="incident", label=inc.id, title=inc.title)
            self.g.add_edge(inc.id, inc.service, rel="affects")
            sol = f"SOL-{inc.id}"
            self.g.add_node(sol, kind="solution", label=inc.resolution[:80])
            self.g.add_edge(inc.id, sol, rel="resolved_by_solution")
            if inc.resolved_by:
                self.g.add_edge(inc.resolved_by, inc.id, rel="resolved")
            for mod in payload.get("modules", []):
                if self.g.has_node(mod):
                    self.g.add_edge(inc.id, mod, rel="touches")

        self._employees = emp_payloads

    def vis(self) -> dict[str, Any]:
        nodes = []
        for n, data in self.g.nodes(data=True):
            nodes.append({"id": n, **data})
        edges = [{"source": u, "target": v, "rel": d.get("rel", "")} for u, v, d in self.g.edges(data=True)]
        return {"nodes": nodes, "edges": edges}

    def expertise_for(self, modules: list[str], incident_ids: list[str] | None = None) -> list[dict]:
        incident_ids = incident_ids or []
        scored = []
        for emp in getattr(self, "_employees", []):
            mods = emp.get("modules", [])
            commits = emp.get("commits", {})
            commit_score = min(1.0, sum(commits.get(m, 0) for m in modules) / 40.0)
            overlap = len(set(mods) & set(modules)) / max(1, len(modules))
            inc_overlap = len(set(emp.get("incidents", [])) & set(incident_ids)) / max(1, len(incident_ids) or 1)
            if not incident_ids:
                inc_overlap = len(emp.get("incidents", [])) / 10.0
            adr = min(1.0, len(emp.get("architecture_decisions", [])) / 3.0)
            score = 0.35 * commit_score + 0.30 * inc_overlap + 0.20 * overlap + 0.15 * adr
            scored.append(
                {
                    "id": emp["id"],
                    "name": emp["name"],
                    "title": emp["title"],
                    "status": emp["status"],
                    "relevance": round(score, 2),
                    "commits": {m: commits.get(m, 0) for m in modules},
                    "incidents": emp.get("incidents", []),
                    "architecture_decisions": emp.get("architecture_decisions", []),
                    "modules": mods,
                    "documentation_coverage": emp.get("documentation_coverage", {}),
                    "knowledge_concentration": emp.get("expertise", {}),
                }
            )
        scored.sort(key=lambda x: x["relevance"], reverse=True)
        return scored

    def knowledge_loss(self, module: str = "Settlement") -> dict:
        if not getattr(self, "_employees", None) or self.g.number_of_nodes() == 0:
            self.rebuild()
        experts = self.expertise_for([module, "Payment"])
        if not experts:
            return {
                "module": f"{module} Service",
                "documentation": 0.43,
                "primary": {"name": "Rahul Sharma", "status": "former", "modules": ["Settlement"]},
                "knowledge_concentration": 0.78,
                "risk": "CRITICAL",
                "secondary": [],
            }
        primary = next((e for e in experts if module in e["modules"]), experts[0])
        docs = primary.get("documentation_coverage", {}).get(module, 0.43)
        concentration = primary.get("knowledge_concentration", {}).get(module, 0.78)
        former = primary["status"] == "former"
        risk = "CRITICAL" if former and concentration > 0.6 and docs < 0.5 else "HIGH" if former else "MEDIUM"
        secondary = [e for e in experts if e["id"] != primary["id"] and e["status"] == "active"][:3]
        return {
            "module": f"{module} Service",
            "documentation": docs,
            "primary": primary,
            "knowledge_concentration": concentration,
            "risk": risk,
            "secondary": secondary,
        }

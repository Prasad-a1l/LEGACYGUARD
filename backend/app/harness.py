from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from datetime import datetime
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from . import agents
from .db import AuditLog, HarnessRun, Incident, KnowledgeItem, SessionLocal, Solution
from .kg import KnowledgeGraph
from .rag import VectorIndex


class HarnessState(TypedDict, total=False):
    run_id: str
    incident_text: str
    scenario: str
    analysis: dict
    current_architecture: dict
    investigation: dict
    code_facts: list
    code_files: list
    historical_matches: list
    internal_sufficient: bool
    evidence_path: str
    compatibility: dict
    external_evidence: list
    experts: list
    primary_expert: dict
    secondary_expert: dict
    domain_owner: dict
    escalation_target: str
    candidates: list
    recommendation_draft: dict
    critic: dict
    confidence: float
    gate: str
    recommendation: dict
    status: str
    human_decision: str
    memory_updates: list
    audit: list


def _merge_list(left: list | None, right: list | None) -> list:
    return (left or []) + (right or [])


class RunHub:
    def __init__(self) -> None:
        self.queues: dict[str, list[asyncio.Queue]] = {}
        self.states: dict[str, dict] = {}
        self.lock = threading.Lock()

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self.lock:
            self.queues.setdefault(run_id, []).append(q)
            snapshot = self.states.get(run_id)
        if snapshot:
            q.put_nowait({"type": "snapshot", "state": snapshot})
        return q

    def emit(self, run_id: str, event: dict) -> None:
        event.setdefault("ts", datetime.utcnow().isoformat() + "Z")
        with self.lock:
            qs = list(self.queues.get(run_id, []))
            state = self.states.get(run_id) or {}
            audit = list(state.get("audit") or [])
            if event.get("type") in {"audit", "node_complete", "node_start"}:
                audit.append(event)
            state = {**state, **(event.get("state_patch") or {})}
            state["audit"] = audit[-80:]
            if event.get("node"):
                state["current_node"] = event.get("node")
            completed = list(state.get("completed_nodes") or [])
            if event.get("type") == "node_complete" and event.get("node") not in completed:
                completed.append(event["node"])
            state["completed_nodes"] = completed
            self.states[run_id] = state
        self._persist_audit(run_id, event)
        for q in qs:
            try:
                q.put_nowait(event)
            except Exception:
                pass

    def patch_state(self, run_id: str, patch: dict) -> dict:
        with self.lock:
            cur = {**self.states.get(run_id, {}), **patch}
            self.states[run_id] = cur
        session = SessionLocal()
        try:
            row = session.get(HarnessRun, run_id)
            if row:
                row.state_json = json.dumps(cur, default=str)
                row.status = cur.get("status") or row.status
                session.commit()
        finally:
            session.close()
        return cur

    def get(self, run_id: str) -> dict:
        with self.lock:
            return dict(self.states.get(run_id) or {})

    def _persist_audit(self, run_id: str, event: dict) -> None:
        msg = event.get("message") or event.get("type") or ""
        if event.get("type") == "node_complete":
            msg = f"{event.get('node')} completed"
        elif event.get("type") == "node_start":
            msg = f"{event.get('node')} started"
        session = SessionLocal()
        try:
            session.add(AuditLog(run_id=run_id, message=msg, node=str(event.get("node") or "")))
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()


HUB = RunHub()


def _node(name: str, fn):
    def wrapped(state: HarnessState) -> dict:
        run_id = state["run_id"]
        HUB.emit(run_id, {"type": "node_start", "node": name, "message": f"{name} started"})
        time.sleep(0.12)
        updates = fn(dict(state)) or {}
        merged = {**dict(state), **updates}
        HUB.emit(
            run_id,
            {
                "type": "node_complete",
                "node": name,
                "message": f"{name} completed",
                "payload": updates,
                "state_patch": updates,
            },
        )
        HUB.patch_state(run_id, {**updates, "current_node": name})
        return updates
    wrapped.__name__ = name
    return wrapped


def _route_evidence(state: HarnessState) -> Literal["compatibility_agent", "external_research_agent"]:
    if state.get("internal_sufficient"):
        return "compatibility_agent"
    return "external_research_agent"


def _route_gate(state: HarnessState) -> Literal["await_human", "escalation"]:
    if state.get("gate") == "ESCALATE":
        return "escalation"
    return "await_human"


def await_human(state: HarnessState) -> dict:
    HUB.emit(
        state["run_id"],
        {
            "type": "awaiting_approval",
            "node": "human_review",
            "message": "Human approval requested",
            "payload": state.get("recommendation"),
            "state_patch": {"status": "awaiting_approval"},
        },
    )
    HUB.patch_state(state["run_id"], {"status": "awaiting_approval"})
    return {"status": "awaiting_approval"}


def escalation(state: HarnessState) -> dict:
    target = state.get("escalation_target") or "Payments Domain Owner"
    HUB.emit(
        state["run_id"],
        {
            "type": "escalated",
            "node": "escalation",
            "message": f"Escalation recommended to {target}",
            "state_patch": {"status": "escalated"},
        },
    )
    return {"status": "escalated"}


def build_graph():
    g = StateGraph(HarnessState)
    g.add_node("load_context", _node("load_context", agents.load_context))
    g.add_node("incident_investigator", _node("incident_investigator", agents.incident_investigator))
    g.add_node("code_archaeologist", _node("code_archaeologist", agents.code_archaeologist))
    g.add_node("historical_incident_agent", _node("historical_incident_agent", agents.historical_incident_agent))
    g.add_node("compatibility_agent", _node("compatibility_agent", agents.compatibility_agent))
    g.add_node("external_research_agent", _node("external_research_agent", agents.external_research_agent))
    g.add_node("expertise_agent", _node("expertise_agent", agents.expertise_agent))
    g.add_node("solution_reasoner", _node("solution_reasoner", agents.solution_reasoner))
    g.add_node("red_team_critic", _node("red_team_critic", agents.red_team_critic))
    g.add_node("evidence_gate", _node("evidence_gate", agents.evidence_gate))
    g.add_node("human_review", _node("human_review", await_human))
    g.add_node("escalation", _node("escalation", escalation))

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "incident_investigator")
    g.add_edge("incident_investigator", "code_archaeologist")
    g.add_edge("code_archaeologist", "historical_incident_agent")
    g.add_conditional_edges(
        "historical_incident_agent",
        _route_evidence,
        {
            "compatibility_agent": "compatibility_agent",
            "external_research_agent": "external_research_agent",
        },
    )
    g.add_edge("compatibility_agent", "expertise_agent")
    g.add_edge("external_research_agent", "expertise_agent")
    g.add_edge("expertise_agent", "solution_reasoner")
    g.add_edge("solution_reasoner", "red_team_critic")
    g.add_edge("red_team_critic", "evidence_gate")
    g.add_conditional_edges(
        "evidence_gate",
        _route_gate,
        {"await_human": "human_review", "escalation": "escalation"},
    )
    g.add_edge("human_review", END)
    g.add_edge("escalation", END)
    return g.compile()


GRAPH = build_graph()


def start_run(incident_text: str, scenario: str = "custom") -> str:
    run_id = str(uuid.uuid4())[:8]
    session = SessionLocal()
    try:
        session.add(
            HarnessRun(
                id=run_id,
                scenario=scenario,
                incident_text=incident_text,
                status="running",
                state_json="{}",
            )
        )
        session.commit()
    finally:
        session.close()
    HUB.patch_state(
        run_id,
        {
            "run_id": run_id,
            "incident_text": incident_text,
            "scenario": scenario,
            "status": "running",
            "completed_nodes": [],
            "audit": [],
        },
    )
    HUB.emit(run_id, {"type": "audit", "message": "Incident received", "node": "START"})

    def _go():
        try:
            GRAPH.invoke(
                {
                    "run_id": run_id,
                    "incident_text": incident_text,
                    "scenario": scenario,
                    "audit": [],
                }
            )
        except Exception as exc:  # noqa: BLE001
            import traceback

            err = f"{exc}\n{traceback.format_exc()}"
            print(err, flush=True)
            HUB.emit(run_id, {"type": "error", "message": str(exc)})
            HUB.patch_state(run_id, {"status": "error", "error": err})

    threading.Thread(target=_go, daemon=True).start()
    return run_id


def apply_decision(run_id: str, action: str, note: str = "") -> dict:
    state = HUB.get(run_id)
    action = action.lower()
    if action == "approve":
        HUB.emit(run_id, {"type": "audit", "message": "Recommendation approved", "node": "human_review"})
        HUB.patch_state(run_id, {"status": "approved", "human_decision": "approve", "human_note": note})
        return HUB.get(run_id)
    if action == "escalate":
        HUB.emit(
            run_id,
            {
                "type": "escalated",
                "message": f"Escalated to {state.get('escalation_target')}",
                "node": "escalation",
            },
        )
        HUB.patch_state(run_id, {"status": "escalated", "human_decision": "escalate"})
        return HUB.get(run_id)
    if action == "reject":
        HUB.emit(run_id, {"type": "audit", "message": "Rejected — returning to Solution Reasoner", "node": "human_review"})
        HUB.patch_state(run_id, {"status": "running", "human_decision": "reject"})

        def _rework():
            partial = {**HUB.get(run_id), "run_id": run_id}
            updates = agents.solution_reasoner(partial)
            HUB.emit(run_id, {"type": "node_complete", "node": "solution_reasoner", "payload": updates, "state_patch": updates})
            merged = {**partial, **updates}
            crit = agents.red_team_critic(merged)
            HUB.emit(run_id, {"type": "node_complete", "node": "red_team_critic", "payload": crit, "state_patch": crit})
            merged.update(crit)
            gate = agents.evidence_gate(merged)
            HUB.emit(run_id, {"type": "node_complete", "node": "evidence_gate", "payload": gate, "state_patch": gate})
            HUB.emit(run_id, {"type": "awaiting_approval", "node": "human_review", "message": "Human approval requested"})
            HUB.patch_state(run_id, {**updates, **crit, **gate, "status": "awaiting_approval"})

        threading.Thread(target=_rework, daemon=True).start()
        return {"status": "rework"}
    return {"error": "unknown action"}


def resolve_run(run_id: str, root_cause: str, actual_fix: str, result: str) -> dict:
    """Closed loop: only VERIFIED human-confirmed outcomes enter memory."""
    state = HUB.get(run_id)
    new_id = f"INC-NEW-{run_id.upper()}"
    session = SessionLocal()
    try:
        session.add(
            Incident(
                id=new_id,
                service=(state.get("investigation") or {}).get("service") or "Payment",
                title=state.get("incident_text") or "Verified incident",
                failure=state.get("incident_text") or "",
                root_cause=root_cause,
                resolution=actual_fix,
                status="resolved",
                verified=True,
                severity="HIGH",
                year=2026,
                date=datetime.utcnow().date().isoformat(),
                resolved_by="HUMAN",
                payload_json=json.dumps(
                    {
                        "id": new_id,
                        "service": (state.get("investigation") or {}).get("service") or "Payment",
                        "title": state.get("incident_text"),
                        "failure": state.get("incident_text"),
                        "root_cause": root_cause,
                        "resolution": actual_fix,
                        "summary": f"Verified resolution: {root_cause}. Fix: {actual_fix}. Result: {result}",
                        "symptoms": " ".join((state.get("investigation") or {}).get("symptoms") or []),
                        "error_signature": "|".join((state.get("investigation") or {}).get("error_signatures") or []),
                        "architecture": state.get("current_architecture") or {},
                        "year": 2026,
                    }
                ),
            )
        )
        session.add(Solution(id=f"SOL-{new_id}", incident_id=new_id, body=actual_fix, verified=True))
        session.add(
            KnowledgeItem(
                id=f"KI-{new_id}",
                kind="verified_resolution",
                title=root_cause,
                body=f"{actual_fix}\n{result}",
                source_type="HISTORICAL",
                verified=True,
            )
        )
        session.commit()
    finally:
        session.close()
    VectorIndex.instance().rebuild()
    KnowledgeGraph.instance().rebuild()
    updates = [
        "Incident Memory",
        "Root Cause Library",
        "Solution Library",
        "Legacy Documentation",
        "Module Knowledge",
        "Engineer Expertise",
        "Knowledge Graph",
    ]
    HUB.emit(run_id, {"type": "memory_updated", "message": "Knowledge successfully updated.", "payload": updates})
    HUB.patch_state(run_id, {"status": "resolved", "memory_updates": updates, "verified_incident_id": new_id})
    return {"incident_id": new_id, "updates": updates}

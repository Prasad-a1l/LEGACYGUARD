from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .analysis import analyze_repo
from .config import CORS_ORIGINS
from .db import AuditLog, SessionLocal, init_db
from .docs_loop import ask_legacy, generate_wiki, run_drift, run_governance
from .harness import HUB, apply_decision, resolve_run, start_run
from .kg import KnowledgeGraph
from .llm import llm_available
from .seed import seed


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed()
    yield


app = FastAPI(title="LEGACYGUARD", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IncidentIn(BaseModel):
    text: str
    scenario: str = "custom"


class DecisionIn(BaseModel):
    action: str
    note: str = ""


class ResolveIn(BaseModel):
    root_cause: str
    actual_fix: str
    result: str = "Incident resolved."


class AskIn(BaseModel):
    question: str


SCENARIOS = {
    "known_timeout": "Payment confirmations are timing out intermittently.",
    "unknown_kafka": "Kafka consumers are repeatedly rebalancing and settlement processing is delayed.",
}


@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm_available(), "product": "LEGACYGUARD"}


@app.post("/api/seed")
def reseed():
    return seed()


@app.post("/api/runs")
def create_run(body: IncidentIn):
    text = SCENARIOS.get(body.scenario, body.text)
    run_id = start_run(text, body.scenario)
    return {"run_id": run_id, "text": text}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    return HUB.get(run_id)


@app.post("/api/runs/{run_id}/decision")
def decide(run_id: str, body: DecisionIn):
    return apply_decision(run_id, body.action, body.note)


@app.post("/api/runs/{run_id}/resolve")
def resolve(run_id: str, body: ResolveIn):
    return resolve_run(run_id, body.root_cause, body.actual_fix, body.result)


@app.get("/api/runs/{run_id}/audit")
def audit(run_id: str):
    session = SessionLocal()
    try:
        rows = session.query(AuditLog).filter(AuditLog.run_id == run_id).order_by(AuditLog.id.asc()).all()
        return [
            {"ts": r.ts.isoformat() + "Z", "message": r.message, "node": r.node}
            for r in rows
        ]
    finally:
        session.close()


@app.websocket("/ws/runs/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str):
    await websocket.accept()
    q = HUB.subscribe(run_id)
    try:
        while True:
            event = await q.get()
            await websocket.send_text(json.dumps(event, default=str))
    except WebSocketDisconnect:
        return


@app.get("/api/wiki")
def wiki():
    return generate_wiki()


@app.get("/api/graph")
def graph():
    return KnowledgeGraph.instance().vis()


@app.get("/api/knowledge-loss")
def knowledge_loss():
    return KnowledgeGraph.instance().knowledge_loss("Settlement")


@app.get("/api/scan")
def scan():
    a = analyze_repo()
    return {
        "agents": [
            "Code Archaeologist",
            "Architecture Agent",
            "API Agent",
            "Test Agent",
            "Documentation Agent",
            "Traceability Agent",
        ],
        "analysis": a,
    }


@app.post("/api/scenarios/drift")
def drift():
    return run_drift()


@app.get("/api/scenarios/governance")
def governance():
    return run_governance()


@app.post("/api/ask")
def ask(body: AskIn):
    return ask_legacy(body.question)

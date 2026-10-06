# LEGACYGUARD

**Living Engineering Memory Harness** — Michelin Harness Engineering Hackathon

> When the engineer leaves, the knowledge doesn't.

Decision-support and knowledge-continuity harness with human approval for operational actions. It does not automatically change production.

## Demo company

**NEXAPAY** · platform **NexaPay Core** (9 years old)

## Stack

| Layer | Technology |
|---|---|
| UI | Next.js 14 + Tailwind |
| API | FastAPI + WebSocket |
| Harness | LangGraph |
| LLM | Gemini (optional) with deterministic fallback |
| Relational | PostgreSQL (SQLite fallback) |
| Vectors | Qdrant (in-process fallback) |
| Graph | NetworkX (Neo4j-style display) |

## Quick start

1. Copy `backend/.env.example` to `backend/.env`. Set `GEMINI_API_KEY` if you want live LLM critic/reasoner text.
2. Optional: `docker compose up -d` for PostgreSQL + Qdrant.
3. Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

4. Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## What is real vs synthetic

**Real:** LangGraph orchestration, AST code analysis, RAG retrieval, incident similarity, compatibility checks, web-search fallback, Red Team node, evidence gate, human approval, audit trail, memory update after verified resolution.

**Synthetic:** NexaPay company, employees, incidents, postmortems, and the legacy repository.

## Five demo scenarios

1. Known incident — *Payment confirmations are timing out intermittently.*
2. Unknown incident — *Kafka consumers are repeatedly rebalancing and settlement processing is delayed.*
3. Documentation drift — API path change `/payments` → `/payments/v2`
4. Contradiction — code / OpenAPI / docs conflict → BLOCK publication
5. Knowledge loss + new-employee brief for Refund Service

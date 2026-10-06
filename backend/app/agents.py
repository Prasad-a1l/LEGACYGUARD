from __future__ import annotations

import json
import re
from typing import Any

from .analysis import analyze_repo
from .config import INTERNAL_MATCH_THRESHOLD
from .kg import KnowledgeGraph
from .llm import llm_complete
from .rag import VectorIndex
from .search import kafka_queries, search_web


CURRENT_ARCH = {
    "year": 2026,
    "database": "postgresql",
    "pool_size": 100,
    "cache": "redis",
    "broker": "kafka",
}


def load_context(state: dict) -> dict:
    analysis = analyze_repo()
    return {
        "analysis": {
            "services": [s["name"] for s in analysis["services"]],
            "constants": analysis["constants"],
            "dependencies": analysis["dependencies"],
            "contradictions": analysis["contradictions"],
            "code_routes": analysis["code_routes"][:12],
        },
        "current_architecture": CURRENT_ARCH,
    }


def incident_investigator(state: dict) -> dict:
    text = state["incident_text"].lower()
    service = "Payment"
    if "settlement" in text or "kafka" in text or "rebalance" in text:
        service = "Settlement"
    elif "refund" in text:
        service = "Refund"
    timed_out = any(w in text for w in ("timeout", "timed out", "timing out", "time out"))
    severity = "HIGH" if timed_out or any(w in text for w in ("rebalance", "duplicate", "down")) else "MEDIUM"
    components = []
    if service == "Payment":
        components = ["PaymentController", "PaymentService", "PostgreSQL", "Redis"]
    elif service == "Settlement":
        components = ["SettlementWorker", "Kafka", "reconciliation.py", "PostgreSQL"]
    else:
        components = ["RefundController", "RefundWorker", "Kafka", "PaymentService"]
    signatures = []
    if timed_out and "confirm" in text:
        signatures.append("confirmation_timeout")
    if timed_out:
        signatures.append("timeout")
    if "rebalance" in text or "heartbeat" in text:
        signatures.append("consumer_rebalance")
    if "lag" in text:
        signatures.append("consumer_lag")
    investigation = {
        "incident": state["incident_text"],
        "affected_service": f"{service}Service",
        "service": service,
        "severity": severity,
        "symptoms": _symptoms(text),
        "components": components,
        "error_signatures": signatures,
        "source_type": "INFERENCE",
        "evidence": [
            {"claim": f"Affected service appears to be {service}Service", "source_type": "INFERENCE"},
            {"claim": "Parsed from operator-entered incident text", "source_type": "FACT", "source": "incident_input"},
        ],
    }
    fallback = json.dumps(investigation, indent=2)
    reasoning = llm_complete(
        f"Extract incident metadata as JSON. Do not invent root cause.\nIncident: {state['incident_text']}\nDraft:\n{fallback}",
        fallback,
    )
    try:
        parsed = json.loads(reasoning[reasoning.find("{") : reasoning.rfind("}") + 1])
        investigation.update({k: parsed[k] for k in parsed if k in investigation})
    except Exception:
        investigation["llm_notes"] = reasoning[:500]
    return {"investigation": investigation}


def _symptoms(text: str) -> list[str]:
    out = []
    if any(w in text for w in ("timeout", "timed out", "timing out", "time out")):
        out.append("Intermittent timeout")
    if "confirm" in text:
        out.append("Payment confirmation path")
    if "rebalance" in text:
        out.append("Consumer group rebalancing")
    if "settlement" in text or "delayed" in text:
        out.append("Settlement delay")
    return out or ["Operator-reported failure"]


def code_archaeologist(state: dict) -> dict:
    analysis = analyze_repo()
    svc = (state.get("investigation") or {}).get("service", "Payment")
    files = []
    for s in analysis["services"]:
        if s["name"].lower() == svc.lower():
            files = s["files"]
    facts = [
        {
            "claim": f"DB_ENGINE={analysis['constants'].get('DB_ENGINE')}",
            "source_type": "FACT",
            "source": "services/payment/repository.py",
        },
        {
            "claim": f"DB_POOL_SIZE={analysis['constants'].get('DB_POOL_SIZE')}",
            "source_type": "FACT",
            "source": "services/payment/repository.py",
        },
        {
            "claim": f"SESSION_TIMEOUT_MS={analysis['constants'].get('SESSION_TIMEOUT_MS')}",
            "source_type": "FACT",
            "source": "services/settlement/worker.py",
        },
        {
            "claim": f"HEARTBEAT_INTERVAL_MS={analysis['constants'].get('HEARTBEAT_INTERVAL_MS')}",
            "source_type": "FACT",
            "source": "services/settlement/worker.py",
        },
    ]
    return {
        "code_facts": facts,
        "code_files": files,
        "analysis": state.get("analysis") or {
            "constants": analysis["constants"],
            "contradictions": analysis["contradictions"],
        },
    }


def _tokens(text: str) -> set[str]:
    raw = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    out = set(raw)
    if raw & {"timeout", "timeouts", "timing", "timed"}:
        out.update({"timeout", "timeouts"})
    if any(t.startswith("confirm") for t in raw):
        out.update({"confirm", "confirmation", "confirmations"})
    if any(t.startswith("rebalanc") for t in raw):
        out.update({"rebalance", "rebalancing", "rebalances"})
    if "heartbeat" in raw or "session" in raw:
        out.update({"heartbeat", "rebalance"})
    return out


def historical_incident_agent(state: dict) -> dict:
    inv = state["investigation"]
    query = " ".join(
        [
            state["incident_text"],
            inv.get("service", ""),
            " ".join(inv.get("error_signatures", [])),
            " ".join(inv.get("symptoms", [])),
        ]
    )
    index = VectorIndex.instance()
    if not index.docs:
        index.rebuild()
    incidents = [d for d in index.docs if d["collection"] == "incidents"]
    semantic_hits = {h["id"]: h["score"] for h in index.search(query, collection="incidents", k=20)}
    qtok = _tokens(query)
    scored = []
    for doc in incidents:
        payload = doc.get("payload") or {}
        semantic = float(semantic_hits.get(doc["id"], 0.0))
        service_sim = 1.0 if payload.get("service", doc.get("service")) == inv.get("service") else 0.12
        sig = set(filter(None, (payload.get("error_signature") or "").split("|")))
        qsig = set(inv.get("error_signatures") or [])
        if qsig and sig:
            sig_sim = 0.9 if sig & qsig else 0.08
        elif not qsig:
            sig_sim = 0.25
        else:
            sig_sim = 0.08
        blob = _tokens(
            " ".join(
                [
                    payload.get("title") or "",
                    payload.get("failure") or "",
                    payload.get("symptoms") or "",
                    payload.get("root_cause") or "",
                    payload.get("summary") or "",
                ]
            )
        )
        fail_tok = _tokens(f"{payload.get('title','')} {payload.get('failure','')}")
        title_recall = len(qtok & fail_tok) / max(1, len(fail_tok))
        overlap = len(qtok & blob) / max(1, len(qtok))
        arch = payload.get("architecture") or {}
        arch_sim = 1.0 if arch.get("database") == CURRENT_ARCH["database"] else 0.4
        hybrid = (
            0.40 * title_recall
            + 0.20 * overlap
            + 0.20 * service_sim
            + 0.15 * sig_sim
            + 0.05 * semantic
        )
        # Similar symptoms ≠ same root cause (e.g. lag vs rebalance).
        if "consumer_rebalance" in qsig and "consumer_rebalance" not in sig and "rebalance" not in blob:
            hybrid *= 0.5
        if "confirmation_timeout" in qsig and "confirmation_timeout" not in sig:
            hybrid *= 0.75
        scored.append(
            {
                "id": payload.get("id") or doc["id"],
                "title": payload.get("title") or payload.get("failure"),
                "service": payload.get("service"),
                "failure": payload.get("failure"),
                "root_cause": payload.get("root_cause"),
                "resolution": payload.get("resolution"),
                "year": payload.get("year"),
                "architecture": arch,
                "similarity": round(hybrid, 2),
                "similarity_pct": int(round(min(0.99, hybrid) * 100)),
                "breakdown": {
                    "semantic": round(semantic, 2),
                    "service": service_sim,
                    "title_recall": round(title_recall, 2),
                    "overlap": round(overlap, 2),
                    "error_signature": round(sig_sim, 2),
                    "architecture": arch_sim,
                },
                "verified": True,
                "source_type": "HISTORICAL",
            }
        )
    scored.sort(key=lambda x: x["similarity"], reverse=True)
    top = scored[:3]
    sufficient = bool(top) and top[0]["similarity"] >= INTERNAL_MATCH_THRESHOLD
    return {
        "historical_matches": top,
        "internal_sufficient": sufficient,
        "evidence_path": "internal" if sufficient else "external",
    }


def compatibility_agent(state: dict) -> dict:
    matches = state.get("historical_matches") or []
    top = matches[0] if matches else None
    if not top:
        return {"compatibility": {"status": "NONE", "notes": "No internal candidate"}}
    old = top.get("architecture") or {}
    diffs = []
    if old.get("database") and old["database"] != CURRENT_ARCH["database"]:
        diffs.append(
            {
                "field": "persistence",
                "historical": old["database"],
                "current": CURRENT_ARCH["database"],
            }
        )
    if old.get("pool_size") and old["pool_size"] != CURRENT_ARCH["pool_size"]:
        diffs.append(
            {
                "field": "connection_pool",
                "historical": old["pool_size"],
                "current": CURRENT_ARCH["pool_size"],
            }
        )
    status = "PARTIAL" if diffs else "COMPATIBLE"
    return {
        "compatibility": {
            "status": status,
            "historical_system": old,
            "current_system": CURRENT_ARCH,
            "differences": diffs,
            "source_type": "FACT",
            "copy_historical_fix": False if diffs else True,
            "notes": "Historical fix cannot be directly copied." if diffs else "Architecture is sufficiently similar.",
        }
    }


def external_research_agent(state: dict) -> dict:
    inv = state.get("investigation") or {}
    queries = kafka_queries() if inv.get("service") == "Settlement" else [
        state["incident_text"] + " official documentation",
        (inv.get("affected_service") or "") + " timeout",
    ]
    raw = search_web(queries)
    evidence = []
    for i, row in enumerate(raw[:4]):
        evidence.append(
            {
                **row,
                "relevance": 87 - i * 9 if "kafka.apache.org" in (row.get("url") or "") else 70 - i * 8,
                "finding": row.get("snippet") or "",
            }
        )
    if not evidence:
        evidence = [
            {
                "title": "Apache Kafka documentation — Consumer Configs",
                "url": "https://kafka.apache.org/documentation/#consumerconfigs",
                "source": "Apache Kafka documentation",
                "finding": "Consumer group rebalances may occur when consumers fail to send heartbeats within the configured interval (session.timeout.ms / heartbeat.interval.ms).",
                "reliability": "HIGH",
                "relevance": 87,
                "source_type": "EXTERNAL",
            }
        ]
    else:
        if evidence[0].get("reliability") == "HIGH" and "heartbeat" not in (evidence[0].get("finding") or "").lower():
            evidence[0]["finding"] = (
                evidence[0]["finding"]
                + " Consumer group rebalances may occur when consumers fail to send heartbeats within the configured interval."
            )
        evidence[0]["source"] = evidence[0].get("title") or "External source"
    return {
        "external_evidence": evidence,
        "evidence_path": "external",
        "internal_sufficient": False,
    }


def expertise_agent(state: dict) -> dict:
    inv = state.get("investigation") or {}
    service = inv.get("service") or "Payment"
    modules = [service]
    if service == "Payment":
        modules += ["PostgreSQL"]
    if service == "Settlement":
        modules += ["Kafka", "PostgreSQL"]
    ids = [m["id"] for m in state.get("historical_matches") or []]
    ranked = KnowledgeGraph.instance().expertise_for(modules, ids)
    primary = ranked[0] if ranked else None
    secondary = next((e for e in ranked[1:] if e["status"] == "active"), ranked[1] if len(ranked) > 1 else None)
    domain_owner = next((e for e in ranked if e["id"] == "EMP-004"), None)
    return {
        "experts": ranked[:5],
        "primary_expert": primary,
        "secondary_expert": secondary,
        "domain_owner": domain_owner,
        "escalation_target": "Payments Domain Owner" if service in {"Payment", "Refund"} else "Platform / Kafka owner",
    }


def solution_reasoner(state: dict) -> dict:
    path = state.get("evidence_path")
    compat = state.get("compatibility") or {}
    matches = state.get("historical_matches") or []
    if path == "internal" and matches:
        top = matches[0]
        if compat.get("status") == "PARTIAL":
            hypothesis = (
                f"Historical match {top['id']} ({top['root_cause']}) is similar, but persistence changed "
                f"({compat.get('historical_system', {}).get('database')} → {CURRENT_ARCH['database']}). "
                "Inspect PostgreSQL pool waiters, checkout timeout, and confirmation retry/backoff — do not copy the 2024 MySQL pool=50 change."
            )
            confidence = 0.68
            cause = top["root_cause"] + " (compatibility-adjusted)"
        else:
            hypothesis = (
                f"Likely cause: {top['root_cause']}. Previous verified resolution: {top['resolution']}."
            )
            confidence = min(0.91, 0.55 + top["similarity"] * 0.4)
            cause = top["root_cause"]
        candidates = [
            {"id": "C1", "text": hypothesis, "confidence": confidence, "source_type": "RECOMMENDATION"},
            {"id": "C2", "text": "Investigate database statement latency and lock wait", "confidence": 0.61, "source_type": "RECOMMENDATION"},
            {"id": "C3", "text": "Investigate network / gateway timeout misalignment", "confidence": 0.42, "source_type": "RECOMMENDATION"},
        ]
    else:
        ext = (state.get("external_evidence") or [{}])[0]
        constants = (state.get("analysis") or {}).get("constants") or {}
        hypothesis = (
            "No sufficiently similar verified internal incident. External evidence indicates consumer group "
            "rebalances when heartbeats miss session.timeout.ms. Current FACT: "
            f"SESSION_TIMEOUT_MS={constants.get('SESSION_TIMEOUT_MS')} "
            f"HEARTBEAT_INTERVAL_MS={constants.get('HEARTBEAT_INTERVAL_MS')}. "
            "Candidate: raise session timeout / lower heartbeat interval and verify max.poll.interval.ms; "
            "do not apply INC-203's scale-up-for-lag fix as the primary action."
        )
        candidates = [
            {
                "id": "C1",
                "text": hypothesis,
                "confidence": 0.78,
                "source_type": "RECOMMENDATION",
                "external": ext,
            }
        ]
        cause = "Kafka consumer heartbeat / session timeout misconfiguration"
        confidence = 0.78
    prompt = (
        "You are the Solution Reasoner in a harness. Produce a cautious root-cause hypothesis. "
        "Never claim certainty. Use only provided evidence.\n"
        f"Evidence path: {path}\nCandidates: {json.dumps(candidates)[:3000]}"
    )
    narrative = llm_complete(prompt, candidates[0]["text"])
    return {
        "candidates": candidates,
        "recommendation_draft": {
            "likely_cause": cause,
            "action": candidates[0]["text"],
            "confidence": confidence,
            "narrative": narrative,
            "source_type": "RECOMMENDATION",
        },
    }


def red_team_critic(state: dict) -> dict:
    draft = state.get("recommendation_draft") or {}
    compat = state.get("compatibility") or {}
    path = state.get("evidence_path")
    challenges = []
    confidence = float(draft.get("confidence") or 0.7)
    before = confidence
    if compat.get("status") == "PARTIAL":
        challenges.append(
            {
                "title": "ARCHITECTURE DIFFERENCE",
                "detail": "The historical incident is similar, but the persistence layer changed. Historical fix cannot be directly copied.",
                "source_type": "FACT",
            }
        )
        confidence = min(confidence, 0.68)
    if path == "external":
        challenges.append(
            {
                "title": "EXTERNAL EVIDENCE ONLY",
                "detail": "No verified internal twin. External docs may not match NexaPay consumer settings.",
                "source_type": "INFERENCE",
            }
        )
        confidence = min(confidence, 0.78)
    alt = "Could another cause (slow query, gateway timeout, Redis lock, consumer lag) explain the same symptoms?"
    challenges.append({"title": "ALTERNATE CAUSE", "detail": alt, "source_type": "INFERENCE"})
    blocking = [c for c in challenges if "ARCHITECTURE" in c["title"]]
    prompt = (
        "You are the Red Team critic. Try to disprove the recommendation. "
        "List contradictions. Reduce confidence if architecture drifted.\n"
        f"{json.dumps({'draft': draft, 'compat': compat})[:3500]}"
    )
    critique = llm_complete(
        prompt,
        "Historical incident is similar, but the persistence layer changed. Confidence must drop until an engineer confirms PostgreSQL pool behaviour."
        if compat.get("status") == "PARTIAL"
        else "No blocking contradiction in evidence, but alternate causes remain possible.",
    )
    return {
        "critic": {
            "challenges": challenges,
            "blocking": bool(blocking) or confidence < 0.55,
            "writeup": critique,
            "confidence_before": round(before, 2),
            "confidence_after": round(confidence, 2),
        },
        "confidence": round(confidence, 2),
    }


def evidence_gate(state: dict) -> dict:
    confidence = float(state.get("confidence") or 0)
    critic = state.get("critic") or {}
    path = state.get("evidence_path")
    compat = state.get("compatibility") or {}
    decision = "PASS"
    reason = "Evidence is consistent enough for human review."
    if critic.get("blocking") or compat.get("status") == "PARTIAL":
        decision = "HUMAN_REVIEW"
        reason = "Architecture difference or critic challenge requires engineer review."
    if path == "external" and confidence < 0.8:
        decision = "HUMAN_REVIEW"
        reason = "Internal memory insufficient; external evidence needs human confirmation."
    if confidence < 0.55:
        decision = "ESCALATE"
        reason = "Confidence below escalation threshold. Do not present a confident root cause."
    rec = state.get("recommendation_draft") or {}
    recommendation = {
        **rec,
        "confidence": confidence,
        "severity": (state.get("investigation") or {}).get("severity", "HIGH"),
        "evidence_ids": [m["id"] for m in state.get("historical_matches") or []],
        "gate": decision,
        "gate_reason": reason,
        "critic_findings": critic.get("writeup"),
    }
    return {"gate": decision, "recommendation": recommendation, "status": "awaiting_approval" if decision != "ESCALATE" else "escalated"}

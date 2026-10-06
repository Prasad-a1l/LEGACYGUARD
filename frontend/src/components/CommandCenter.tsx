"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE, api, connectRun } from "@/lib/api";

const NODES = [
  { id: "incident_investigator", label: "Incident Investigator" },
  { id: "code_archaeologist", label: "Current System Analyzer" },
  { id: "historical_incident_agent", label: "Historical Incident Agent" },
  { id: "compatibility_agent", label: "Compatibility Agent" },
  { id: "external_research_agent", label: "External Research" },
  { id: "solution_reasoner", label: "Solution Reasoner" },
  { id: "red_team_critic", label: "Red Team Critic" },
  { id: "evidence_gate", label: "Evidence Gate" },
];

type RunState = Record<string, unknown>;

export default function CommandCenter() {
  const [text, setText] = useState(
    "Payment confirmations are timing out intermittently."
  );
  const [runId, setRunId] = useState<string | null>(null);
  const [state, setState] = useState<RunState>({});
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const [busy, setBusy] = useState(false);
  const [rootCause, setRootCause] = useState("Connection pool exhaustion");
  const [fix, setFix] = useState("Pool size increased from 50 → 100; backoff verified on PostgreSQL.");
  const [resolved, setResolved] = useState<Record<string, unknown> | null>(null);

  const completed = (state.completed_nodes as string[]) || [];
  const current = (state.current_node as string) || "";
  const inv = (state.investigation as Record<string, unknown>) || {};
  const matches = (state.historical_matches as Record<string, unknown>[]) || [];
  const rec = (state.recommendation as Record<string, unknown>) || {};
  const critic = (state.critic as Record<string, unknown>) || {};
  const primary = state.primary_expert as Record<string, unknown> | undefined;
  const secondary = state.secondary_expert as Record<string, unknown> | undefined;
  const compat = (state.compatibility as Record<string, unknown>) || {};
  const external = (state.external_evidence as Record<string, unknown>[]) || [];

  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  async function start(scenario: string, incident?: string) {
    setBusy(true);
    setResolved(null);
    setEvents([]);
    setState({ status: "running", completed_nodes: [] });
    const body = await api<{ run_id: string; text: string }>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ scenario, text: incident || text }),
    });
    setRunId(body.run_id);
    setText(body.text);
    wsRef.current?.close();
    wsRef.current = connectRun(body.run_id, (e) => {
      setEvents((prev) => [...prev, e]);
      if (e.state_patch && typeof e.state_patch === "object") {
        setState((s) => ({ ...s, ...(e.state_patch as object) }));
      }
      if (e.type === "snapshot" && e.state) {
        setState(e.state as RunState);
      }
      if (e.type === "awaiting_approval" || e.type === "escalated") {
        setState((s) => ({ ...s, status: e.type === "escalated" ? "escalated" : "awaiting_approval" }));
      }
      if (e.node) {
        setState((s) => {
          const done = new Set((s.completed_nodes as string[]) || []);
          if (e.type === "node_complete") done.add(String(e.node));
          return { ...s, current_node: e.node, completed_nodes: [...done] };
        });
      }
    });
    poll(body.run_id);
    setBusy(false);
  }

  async function poll(id: string) {
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 700));
      try {
        const s = await api<RunState>(`/api/runs/${id}`);
        setState((prev) => ({ ...prev, ...s }));
        if (["awaiting_approval", "escalated", "approved", "resolved", "error"].includes(String(s.status))) {
          break;
        }
      } catch {
        break;
      }
    }
  }

  async function decide(action: string) {
    if (!runId) return;
    await api(`/api/runs/${runId}/decision`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
    poll(runId);
  }

  async function closeLoop() {
    if (!runId) return;
    const out = await api<Record<string, unknown>>(`/api/runs/${runId}/resolve`, {
      method: "POST",
      body: JSON.stringify({
        root_cause: rootCause,
        actual_fix: fix,
        result: "Incident resolved.",
      }),
    });
    setResolved(out);
    poll(runId);
  }

  const mark = (id: string) => {
    if (completed.includes(id)) return "✓";
    if (current === id && state.status === "running") return "●";
    if (id === "external_research_agent" && completed.includes("compatibility_agent")) return "–";
    if (id === "compatibility_agent" && completed.includes("external_research_agent")) return "–";
    return "○";
  };

  const diffs = (compat.differences as Record<string, unknown>[]) || [];

  return (
    <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
      <div className="space-y-4">
        <section className="panel">
          <div className="flex flex-wrap gap-2 mb-3">
            <button className="btn" onClick={() => start("known_timeout")} disabled={busy}>
              1. Known timeout
            </button>
            <button className="btn" onClick={() => start("unknown_kafka")} disabled={busy}>
              2. Unknown Kafka
            </button>
          </div>
          <textarea
            className="w-full bg-black/40 border border-line rounded-md p-3 text-sm font-mono min-h-20"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="btn mt-3" onClick={() => start("custom", text)} disabled={busy}>
            Run harness
          </button>
        </section>

        <section className="panel">
          <div className="kicker text-danger">ACTIVE INCIDENT</div>
          <h2 className="text-xl mt-1">{String(inv.incident || text)}</h2>
          <p className="text-mute text-sm mt-2">
            Service: {String(inv.affected_service || "—")} · Severity:{" "}
            <span className="text-danger font-semibold">{String(inv.severity || "—")}</span>
            {runId ? ` · Run ${runId}` : ""}
          </p>
        </section>

        <section className="panel">
          <div className="kicker">HARNESS EXECUTION</div>
          <ul className="mt-3 space-y-1.5 font-mono text-sm">
            {NODES.map((n) => (
              <li key={n.id} className="flex gap-3">
                <span className={mark(n.id) === "✓" ? "text-ok" : mark(n.id) === "●" ? "text-accent" : "text-mute"}>
                  {mark(n.id)}
                </span>
                <span>{n.label}</span>
              </li>
            ))}
          </ul>
        </section>

        {matches.length > 0 && (
          <section className="panel">
            <div className="kicker">HISTORICAL MATCH</div>
            <ul className="mt-3 space-y-2">
              {matches.map((m) => (
                <li key={String(m.id)} className="flex justify-between font-mono">
                  <span>{String(m.id)} · {String(m.failure)}</span>
                  <span className="text-accent">{String(m.similarity_pct)}%</span>
                </li>
              ))}
            </ul>
            {matches[0] && (
              <p className="mt-3 text-sm text-mute">
                Root cause: <span className="text-fg">{String(matches[0].root_cause)}</span>
                <br />
                Previous resolution: {String(matches[0].resolution)}
              </p>
            )}
            {state.evidence_path === "external" && (
              <p className="mt-3 text-warn text-sm">
                No sufficiently similar verified incident. Switching to external evidence.
              </p>
            )}
          </section>
        )}

        {diffs.length > 0 && (
          <section className="panel border-warn/40">
            <div className="kicker text-warn">ARCHITECTURE DIFFERENCE</div>
            {diffs.map((d) => (
              <p key={String(d.field)} className="mt-2 text-sm">
                {String(d.field)}: <span className="text-mute">{String(d.historical)}</span> →{" "}
                <span className="text-fg">{String(d.current)}</span>
              </p>
            ))}
            <p className="text-sm mt-2">{String(compat.notes)}</p>
          </section>
        )}

        {external.length > 0 && (
          <section className="panel">
            <div className="kicker">EXTERNAL EVIDENCE</div>
            {external.slice(0, 3).map((e, i) => (
              <div key={i} className="mt-3 text-sm">
                <div className="text-accent">
                  {String(e.source || e.title)} · {String(e.reliability)} · {String(e.relevance)}%
                </div>
                <p className="text-mute mt-1">{String(e.finding || e.snippet)}</p>
                {e.url ? (
                  <a className="text-xs underline text-mute" href={String(e.url)} target="_blank">
                    {String(e.url)}
                  </a>
                ) : null}
              </div>
            ))}
          </section>
        )}
      </div>

      <div className="space-y-4">
        {primary && (
          <section className="panel">
            <div className="kicker">RELEVANT ENGINEERING EXPERT</div>
            <h3 className="text-lg mt-1">{String(primary.name)}</h3>
            <p className="text-sm text-mute">{String(primary.title)} · relevance {(Number(primary.relevance) * 100).toFixed(0)}%</p>
            <ul className="text-sm mt-2 space-y-1">
              <li>✓ commits on involved modules</li>
              <li>✓ {(primary.incidents as string[])?.length || 0} related incidents</li>
              <li>✓ {(primary.architecture_decisions as string[])?.length || 0} architecture decisions</li>
            </ul>
            {primary.status === "former" && (
              <p className="text-warn mt-2 text-sm">⚠ Rahul is no longer active.</p>
            )}
            {secondary && (
              <div className="mt-4 pt-3 border-t border-line">
                <div className="kicker">SECONDARY EXPERT</div>
                <p className="mt-1">
                  {String(secondary.name)} · {(Number(secondary.relevance) * 100).toFixed(0)}%
                </p>
              </div>
            )}
            <p className="text-sm mt-3">
              Escalation recommended to {String(state.escalation_target || "Payments Domain Owner")}.
            </p>
          </section>
        )}

        {rec.likely_cause && (
          <section className="panel">
            <div className="kicker">RECOMMENDATION</div>
            <p className="mt-2">Likely cause: {String(rec.likely_cause)}</p>
            <p className="text-sm mt-1">
              Confidence: {(Number(rec.confidence) * 100).toFixed(0)}% · Severity: {String(rec.severity)}
            </p>
            <p className="text-sm text-mute mt-2">{String(rec.action)}</p>
            {critic.writeup && (
              <p className="text-sm mt-3 border-t border-line pt-3">
                <span className="text-warn">Critic:</span> {String(critic.writeup)}
                {critic.confidence_before != null && (
                  <span className="block mt-1 font-mono">
                    Confidence {Number(critic.confidence_before) * 100}% → {Number(critic.confidence_after) * 100}%
                  </span>
                )}
              </p>
            )}
            <div className="flex flex-wrap gap-2 mt-4">
              <button className="btn-ok" onClick={() => decide("approve")}>
                APPROVE
              </button>
              <button className="btn" onClick={() => decide("reject")}>
                REJECT
              </button>
              <button className="btn-danger" onClick={() => decide("escalate")}>
                ESCALATE
              </button>
            </div>
          </section>
        )}

        {state.status === "approved" && (
          <section className="panel">
            <div className="kicker text-ok">ROOT CAUSE CONFIRMED</div>
            <input className="field mt-2" value={rootCause} onChange={(e) => setRootCause(e.target.value)} />
            <div className="kicker mt-3">ACTUAL FIX</div>
            <textarea className="field mt-2 min-h-16" value={fix} onChange={(e) => setFix(e.target.value)} />
            <button className="btn-ok mt-3" onClick={closeLoop}>
              Record verified resolution
            </button>
            {resolved && (
              <p className="text-ok text-sm mt-3">
                Knowledge successfully updated. Future similar incidents can use this verified resolution.
              </p>
            )}
          </section>
        )}

        <section className="panel">
          <div className="kicker">AUDIT TRAIL</div>
          <ul className="mt-2 font-mono text-xs space-y-1 max-h-64 overflow-auto">
            {events
              .filter((e) => e.message || e.type === "audit")
              .map((e, i) => (
                <li key={i} className="text-mute">
                  {String(e.ts || "").slice(11, 19)} {String(e.message || e.type)}
                </li>
              ))}
            {!events.length && <li className="text-mute">Waiting for harness…</li>}
          </ul>
          <p className="text-[10px] text-mute mt-2">API {API_BASE}</p>
        </section>
      </div>
    </div>
  );
}

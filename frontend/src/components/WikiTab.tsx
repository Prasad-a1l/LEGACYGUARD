"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function WikiTab() {
  const [wiki, setWiki] = useState<Record<string, unknown> | null>(null);
  const [ask, setAsk] = useState("I just joined the payments team. Explain the refund service.");
  const [brief, setBrief] = useState<Record<string, unknown> | null>(null);
  const [drift, setDrift] = useState<Record<string, unknown> | null>(null);
  const [gov, setGov] = useState<Record<string, unknown> | null>(null);
  const [loss, setLoss] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api<Record<string, unknown>>("/api/wiki").then(setWiki).catch(() => setWiki(null));
  }, []);

  const apis = (wiki?.apis as { code?: { path: string }[] }) || {};

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="panel lg:col-span-2">
        <div className="kicker">LIVING SOFTWARE WIKI</div>
        <p className="text-sm text-mute mt-2">
          CodeWiki-style understanding of NexaPay Core, plus what the organization learned when that software failed.
        </p>
        <pre className="mt-3 text-xs text-mute whitespace-pre-wrap font-mono">
          {String(wiki?.architecture || "Loading architecture…")}
        </pre>
      </section>

      <section className="panel">
        <div className="kicker">CODE ROUTES (FACT)</div>
        <ul className="mt-2 font-mono text-sm space-y-1">
          {(apis.code || []).map((r, i) => (
            <li key={i}>{r.path}</li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <div className="kicker">LEGACY KNOWLEDGE</div>
        <ul className="mt-2 text-sm space-y-1">
          {((wiki?.legacy as string[]) || []).map((x) => (
            <li key={x}>• {x}</li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <div className="kicker">ASK THE LEGACY SYSTEM</div>
        <textarea className="field mt-2 min-h-20" value={ask} onChange={(e) => setAsk(e.target.value)} />
        <button
          className="btn mt-2"
          onClick={async () => setBrief(await api("/api/ask", { method: "POST", body: JSON.stringify({ question: ask }) }))}
        >
          Generate engineering brief
        </button>
        {brief && (
          <div className="mt-3 text-sm space-y-2">
            <h3 className="text-lg">{String(brief.title)}</h3>
            <p>{String(brief.purpose)}</p>
            <p className="text-mute">Architecture: {String(brief.architecture)}</p>
            <p>Known failure modes: {((brief.failure_modes as string[]) || []).join(" · ")}</p>
            <p>Historical incidents: {((brief.incidents as string[]) || []).join(", ")}</p>
            <p>Technical debt: {((brief.technical_debt as string[]) || []).join("; ")}</p>
            <ul>
              {((brief.engineers as { name: string; relevance: number; status: string }[]) || []).map((e) => (
                <li key={e.name}>
                  {e.name} — {(e.relevance * 100).toFixed(0)}% ({e.status})
                </li>
              ))}
            </ul>
            {((brief.modules as { file: string; why: string }[]) || []).map((m) => (
              <a key={m.file} className="block text-accent text-xs underline" href="#">
                [View source] {m.file} — {m.why}
              </a>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="kicker">SCENARIOS 3–5</div>
        <div className="flex flex-wrap gap-2 mt-2">
          <button className="btn" onClick={async () => setDrift(await api("/api/scenarios/drift", { method: "POST" }))}>
            3. Documentation drift
          </button>
          <button className="btn" onClick={async () => setGov(await api("/api/scenarios/governance"))}>
            4. Contradiction gate
          </button>
          <button className="btn" onClick={async () => setLoss(await api("/api/knowledge-loss"))}>
            5. Knowledge loss
          </button>
        </div>

        {drift && (
          <div className="mt-4 text-sm">
            <div className="kicker text-danger">CHANGE DETECTED</div>
            <p className="mt-1 font-mono">
              {String((drift.change as { from: string }).from)} → {String((drift.change as { to: string }).to)}
            </p>
            <ul className="mt-2">
              {(((drift.change as { impact: { artifact: string; severity: string }[] }).impact) || []).map((i) => (
                <li key={i.artifact}>
                  {i.severity === "red" ? "🔴" : i.severity === "orange" ? "🟠" : "🟢"} {i.artifact}
                </li>
              ))}
            </ul>
            <p className="text-mute mt-2">{String(drift.critic)}</p>
          </div>
        )}

        {gov && (
          <div className="mt-4 border border-danger/50 rounded-md p-3">
            <div className="kicker text-danger">GOVERNANCE GATE FAILED</div>
            <p className="mt-2 font-semibold">API CONTRACT CONFLICT</p>
            <p className="font-mono text-sm mt-2">Code: {String((gov.conflict as { code: string }).code)}</p>
            <p className="font-mono text-sm">OpenAPI: {String((gov.conflict as { openapi: string }).openapi)}</p>
            <p className="font-mono text-sm">Documentation: {String((gov.conflict as { documentation: string }).documentation)}</p>
            <p className="mt-2">Authoritative contract: UNKNOWN</p>
            <p className="mt-2">ACTION: {String(gov.action)}</p>
            <p>ESCALATE: {String(gov.escalate)}</p>
            <p className="text-mute mt-2 italic">{String(gov.message)}</p>
          </div>
        )}

        {loss && (
          <div className="mt-4 text-sm">
            <div className="kicker text-danger">KNOWLEDGE CONTINUITY</div>
            <p className="mt-1">{String(loss.module)}</p>
            <p>Documentation: {(Number(loss.documentation) * 100).toFixed(0)}%</p>
            <p>
              Primary historical expert: {String((loss.primary as { name: string }).name)} (
              {String((loss.primary as { status: string }).status)})
            </p>
            <p>Knowledge concentration: {(Number(loss.knowledge_concentration) * 100).toFixed(0)}%</p>
            <p className="text-danger">Risk: {String(loss.risk)}</p>
            <p className="mt-2 text-ok">
              LEGACYGUARD ACTION: generated missing documentation paths, reconstructed architecture, linked historical
              incidents, identified secondary experts, created onboarding knowledge pack.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

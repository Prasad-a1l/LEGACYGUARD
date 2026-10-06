"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type Node = { id: string; kind?: string; label?: string; status?: string };
type Edge = { source: string; target: string; rel?: string };

const KIND_COLOR: Record<string, string> = {
  engineer: "#f59e0b",
  module: "#22d3ee",
  incident: "#f87171",
  solution: "#4ade80",
  api: "#a78bfa",
  dependency: "#94a3b8",
  document: "#60a5fa",
  test: "#f472b6",
  requirement: "#fbbf24",
};

export default function GraphTab() {
  const [data, setData] = useState<{ nodes: Node[]; edges: Edge[] }>({ nodes: [], edges: [] });
  const [focus, setFocus] = useState<string>("Refund");

  useEffect(() => {
    api<{ nodes: Node[]; edges: Edge[] }>("/api/graph").then(setData).catch(() => null);
  }, []);

  const view = useMemo(() => {
    const related = new Set<string>([focus]);
    for (const e of data.edges) {
      if (e.source === focus || e.target === focus) {
        related.add(e.source);
        related.add(e.target);
      }
    }
    const nodes = data.nodes.filter((n) => related.has(n.id) || n.kind === "module");
    const ids = new Set(nodes.map((n) => n.id));
    const edges = data.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    return { nodes: nodes.slice(0, 40), edges: edges.slice(0, 60) };
  }, [data, focus]);

  const w = 860;
  const h = 520;
  const groups = ["requirement", "engineer", "module", "api", "incident", "solution", "dependency", "document", "test"];
  const pos = new Map<string, { x: number; y: number }>();
  const byKind: Record<string, Node[]> = {};
  for (const n of view.nodes) {
    const k = n.kind || "module";
    byKind[k] = byKind[k] || [];
    byKind[k].push(n);
  }
  groups.forEach((g, gi) => {
    const col = byKind[g] || [];
    col.forEach((n, i) => {
      pos.set(n.id, {
        x: 70 + gi * 90,
        y: 50 + i * 48 + (gi % 2) * 16,
      });
    });
  });

  return (
    <div className="space-y-4">
      <section className="panel">
        <div className="kicker">ENGINEERING KNOWLEDGE GRAPH</div>
        <p className="text-sm text-mute mt-1">
          NetworkX graph rendered Neo4j-style: Engineer → Module → Incident → Solution
        </p>
        <div className="flex flex-wrap gap-2 mt-3">
          {["Payment", "Refund", "Settlement", "EMP-001", "INC-155", "REQ-023"].map((id) => (
            <button key={id} className={`btn ${focus === id ? "ring-1 ring-accent" : ""}`} onClick={() => setFocus(id)}>
              {id}
            </button>
          ))}
        </div>
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full mt-4 h-[520px] bg-black/30 rounded-md">
          {view.edges.map((e, i) => {
            const a = pos.get(e.source);
            const b = pos.get(e.target);
            if (!a || !b) return null;
            return (
              <g key={i}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#334155" strokeWidth="1" />
              </g>
            );
          })}
          {view.nodes.map((n) => {
            const p = pos.get(n.id);
            if (!p) return null;
            return (
              <g key={n.id} onClick={() => setFocus(n.id)} className="cursor-pointer">
                <circle cx={p.x} cy={p.y} r="8" fill={KIND_COLOR[n.kind || "module"] || "#22d3ee"} />
                <text x={p.x + 12} y={p.y + 4} fill="#e2e8f0" fontSize="10">
                  {(n.label || n.id).slice(0, 28)}
                  {n.status === "former" ? " ✕" : ""}
                </text>
              </g>
            );
          })}
        </svg>
        <div className="flex flex-wrap gap-3 text-xs text-mute mt-2">
          {Object.entries(KIND_COLOR).map(([k, c]) => (
            <span key={k} className="flex items-center gap-1">
              <span className="inline-block w-2 h-2 rounded-full" style={{ background: c }} />
              {k}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}

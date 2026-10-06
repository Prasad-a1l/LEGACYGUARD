"use client";

import { useState } from "react";
import CommandCenter from "@/components/CommandCenter";
import WikiTab from "@/components/WikiTab";
import GraphTab from "@/components/GraphTab";

const TABS = [
  { id: "cc", label: "Engineering Command Center" },
  { id: "wiki", label: "Living Software Wiki" },
  { id: "graph", label: "Knowledge Graph" },
] as const;

export default function Home() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("cc");

  return (
    <div className="min-h-screen">
      <header className="border-b border-line px-6 py-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-[11px] tracking-[0.35em] text-accent">LEGACYGUARD</div>
          <h1 className="text-2xl md:text-3xl font-semibold">Living Engineering Memory Harness</h1>
          <p className="text-mute text-sm mt-1">
            NexaPay Core · decision support with human approval · not an autonomous production fixer
          </p>
        </div>
        <nav className="flex flex-wrap gap-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 rounded-md text-sm border ${
                tab === t.id ? "border-accent text-accent bg-accent/10" : "border-line text-mute"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>
      <main className="p-4 md:p-6">
        {tab === "cc" && <CommandCenter />}
        {tab === "wiki" && <WikiTab />}
        {tab === "graph" && <GraphTab />}
      </main>
    </div>
  );
}

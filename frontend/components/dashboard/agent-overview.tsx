"use client";

import { useEffect, useState } from "react";
import { Bot, Database, Loader2, SlidersHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api, type Agent, type Document } from "@/lib/api/client";

export function AgentOverview({ agentId }: { agentId: string }) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.getAgent(agentId), api.listDocuments(agentId)])
      .then(([nextAgent, nextDocuments]) => { setAgent(nextAgent); setDocuments(nextDocuments); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load agent"));
  }, [agentId]);

  if (error) return <Card className="p-6 text-rose-700">{error}</Card>;
  if (!agent) return <div className="grid min-h-64 place-items-center"><Loader2 className="size-6 animate-spin text-primary" /></div>;

  const ready = documents.filter((document) => document.status === "ready").length;
  return (
    <>
      <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-3"><h1 className="text-3xl font-bold tracking-tight">{agent.name}</h1><Badge tone="success">Active</Badge></div>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">{agent.system_prompt}</p>
        </div>
        <Badge tone="primary">{agent.llm_provider} · {agent.model}</Badge>
      </div>
      <div className="grid gap-5 md:grid-cols-3">
        {[
          { label: "Ready documents", value: `${ready}/${documents.length}`, icon: Database, color: "bg-sky-50 text-sky-600" },
          { label: "Retrieval depth", value: agent.top_k ?? 5, icon: SlidersHorizontal, color: "bg-violet-50 text-violet-600" },
          { label: "Reranker", value: agent.use_reranker ? "Enabled" : "Off", icon: Bot, color: "bg-emerald-50 text-emerald-600" },
        ].map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="p-5">
            <span className={`grid size-10 place-items-center rounded-xl ${color}`}><Icon className="size-5" /></span>
            <p className="mt-4 text-2xl font-bold">{value}</p><p className="mt-1 text-sm text-slate-500">{label}</p>
          </Card>
        ))}
      </div>
      <Card className="mt-5 p-6">
        <h2 className="font-semibold">Configuration</h2>
        <dl className="mt-5 grid gap-5 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="text-slate-400">Temperature</dt><dd className="mt-1 font-semibold">{agent.temperature}</dd></div>
          <div><dt className="text-slate-400">Chunking</dt><dd className="mt-1 font-semibold capitalize">{agent.chunk_strategy}</dd></div>
          <div><dt className="text-slate-400">Chunk size</dt><dd className="mt-1 font-semibold">{agent.chunk_size_tokens} tokens</dd></div>
          <div><dt className="text-slate-400">Tools</dt><dd className="mt-1 font-semibold">{agent.tools?.length ?? 0} enabled</dd></div>
        </dl>
      </Card>
    </>
  );
}

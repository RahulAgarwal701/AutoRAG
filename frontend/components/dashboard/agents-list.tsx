"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Bot, Loader2, Plus } from "lucide-react";

import { EmptyState } from "@/components/dashboard/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, type Agent } from "@/lib/api/client";
import { formatDate } from "@/lib/format";

export function AgentsList() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listAgents()
      .then(setAgents)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load agents"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="grid min-h-72 place-items-center"><Loader2 className="size-6 animate-spin text-primary" /></div>;
  }
  if (error) return <Card className="p-6 text-sm text-rose-700">{error}</Card>;
  if (!agents.length) {
    return (
      <EmptyState action={<Button asChild><Link href="/dashboard/agents/new"><Plus className="mr-2 size-4" />Create agent</Link></Button>} />
    );
  }
  return (
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
      {agents.map((agent) => (
        <Card key={agent.id} className="group overflow-hidden p-0 transition hover:-translate-y-0.5 hover:shadow-lg">
          <div className="h-1 bg-gradient-to-r from-violet-500 via-indigo-500 to-sky-400" />
          <div className="p-6">
            <div className="flex items-start justify-between gap-4">
              <span className="grid size-11 place-items-center rounded-2xl bg-slate-950 text-white">
                <Bot className="size-5" />
              </span>
              <Badge tone="success"><span className="mr-1.5 size-1.5 rounded-full bg-emerald-500" />Active</Badge>
            </div>
            <h2 className="mt-5 truncate text-lg font-semibold">{agent.name}</h2>
            <p className="mt-1 line-clamp-2 min-h-10 text-sm leading-5 text-slate-500">{agent.system_prompt}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              <Badge tone="primary">{agent.llm_provider}</Badge>
              <Badge>{agent.model}</Badge>
            </div>
            <div className="mt-6 flex items-center justify-between border-t pt-4">
              <span className="text-xs text-slate-400">Created {formatDate(agent.created_at)}</span>
              <Link href={`/dashboard/agents/${agent.id}`} className="focus-ring rounded-lg text-sm font-semibold text-primary">
                Manage <ArrowRight className="ml-1 inline size-3.5 transition group-hover:translate-x-0.5" />
              </Link>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

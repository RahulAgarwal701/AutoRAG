"use client";

import { useEffect, useState } from "react";
import { Bot, Database, KeyRound, Layers3, Loader2, MessagesSquare } from "lucide-react";

import { Card } from "@/components/ui/card";
import { api, type UsageSummary } from "@/lib/api/client";

export function UsageDashboard() {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.usage().then(setUsage).catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load usage")); }, []);
  if (error) return <Card className="p-6 text-rose-700">{error}</Card>;
  if (!usage) return <div className="grid min-h-72 place-items-center"><Loader2 className="size-6 animate-spin text-primary" /></div>;
  const metrics = [
    { label: "Agents", value: usage.agents, icon: Bot, tone: "bg-violet-50 text-violet-600" },
    { label: "Documents", value: usage.documents.total, icon: Database, tone: "bg-sky-50 text-sky-600" },
    { label: "Indexed chunks", value: usage.documents.indexed_chunks, icon: Layers3, tone: "bg-emerald-50 text-emerald-600" },
    { label: "Conversations", value: usage.chat_sessions, icon: MessagesSquare, tone: "bg-amber-50 text-amber-600" },
    { label: "Active API keys", value: usage.active_api_keys, icon: KeyRound, tone: "bg-rose-50 text-rose-600" },
  ];
  const denominator = Math.max(usage.documents.total, 1);
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{metrics.map(({ label, value, icon: Icon, tone }) => <Card key={label} className="p-5"><span className={`grid size-10 place-items-center rounded-xl ${tone}`}><Icon className="size-5" /></span><p className="mt-4 text-2xl font-bold">{value.toLocaleString()}</p><p className="mt-1 text-sm text-slate-500">{label}</p></Card>)}</div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card className="p-6"><h2 className="font-semibold">Document processing</h2><p className="mt-1 text-sm text-slate-500">Current state across every agent.</p><div className="mt-6 h-3 overflow-hidden rounded-full bg-slate-100">{([['ready','bg-emerald-500'],['processing','bg-violet-500'],['pending','bg-amber-400'],['failed','bg-rose-500']] as const).map(([key,color]) => <span key={key} className={`inline-block h-full ${color}`} style={{ width: `${(usage.documents[key] / denominator) * 100}%` }} />)}</div><div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">{(['ready','processing','pending','failed'] as const).map((key) => <div key={key}><p className="text-xl font-bold">{usage.documents[key]}</p><p className="text-xs capitalize text-slate-500">{key}</p></div>)}</div></Card>
        <Card className="p-6"><h2 className="font-semibold">Chat activity</h2><div className="mt-7"><p className="text-4xl font-bold tracking-tight">{usage.messages.toLocaleString()}</p><p className="mt-1 text-sm text-slate-500">messages persisted</p></div><p className="mt-7 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-500">Token counts are emitted in structured request logs. Persistent billing analytics can be added when a metering store is introduced.</p></Card>
      </div>
    </>
  );
}

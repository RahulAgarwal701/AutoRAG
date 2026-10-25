"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Copy, KeyRound, Loader2, Plus, ShieldCheck } from "lucide-react";

import { PageHeader } from "@/components/dashboard/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, type ApiKey, type ApiKeyCreated } from "@/lib/api/client";
import { formatDate } from "@/lib/format";

export function ApiKeyManager({ agentId }: { agentId: string }) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => api.listApiKeys(agentId).then(setKeys).finally(() => setLoading(false)), [agentId]);
  useEffect(() => { void load().catch((reason) => setError(reason.message)); }, [load]);

  async function create() {
    try { const key = await api.createApiKey(agentId); setCreated(key); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create key"); }
  }
  async function revoke(key: ApiKey) {
    if (!window.confirm(`Revoke ${key.prefix}…? Existing integrations will stop working.`)) return;
    try { await api.revokeApiKey(agentId, key.id); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to revoke key"); }
  }
  async function copy() {
    if (!created) return;
    await navigator.clipboard.writeText(created.key); setCopied(true); window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <>
      <PageHeader title="API keys" description="Authenticate server-side calls to this agent. Never expose these keys in browser code." action={<Button onClick={() => void create()}><Plus className="mr-2 size-4" />Create key</Button>} />
      {error && <p className="mb-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      {created && (
        <Card className="mb-6 border-emerald-200 bg-emerald-50/80 p-5">
          <div className="flex gap-3"><ShieldCheck className="mt-0.5 size-5 shrink-0 text-emerald-600" /><div className="min-w-0 flex-1"><h2 className="font-semibold text-emerald-950">Copy your key now</h2><p className="mt-1 text-sm text-emerald-700">For security, the full value will not be shown again.</p><div className="mt-4 flex gap-2"><code className="min-w-0 flex-1 overflow-x-auto rounded-xl bg-white px-3 py-2.5 text-sm text-slate-800 ring-1 ring-emerald-200">{created.key}</code><Button variant="outline" onClick={() => void copy()}>{copied ? <Check className="size-4" /> : <Copy className="size-4" />}</Button></div></div></div>
        </Card>
      )}
      <Card className="overflow-hidden">
        {loading ? <div className="grid min-h-52 place-items-center"><Loader2 className="size-5 animate-spin" /></div> : !keys.length ? <div className="px-6 py-16 text-center"><KeyRound className="mx-auto size-8 text-slate-300" /><p className="mt-3 text-sm text-slate-500">No API keys yet.</p></div> : <div className="divide-y">{keys.map((key) => <div key={key.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><code className="text-sm font-semibold">{key.prefix}••••••••</code><Badge tone={key.revoked ? "danger" : "success"}>{key.revoked ? "Revoked" : "Active"}</Badge></div><p className="mt-1 text-xs text-slate-400">Created {formatDate(key.created_at)} · Last used {formatDate(key.last_used_at as string | null)}</p></div>{!key.revoked && <Button variant="outline" size="sm" onClick={() => void revoke(key)} className="text-rose-600">Revoke</Button>}</div>)}</div>}
      </Card>
    </>
  );
}

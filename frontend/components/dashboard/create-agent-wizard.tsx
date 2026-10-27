"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Clipboard,
  CloudUpload,
  Code2,
  FileText,
  KeyRound,
  Loader2,
  Rocket,
  Settings2,
  Sparkles,
} from "lucide-react";

import { ChatPlayground } from "@/components/dashboard/chat-playground";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, type ApiKeyCreated, type Document } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const steps = [
  { label: "Purpose", icon: Sparkles },
  { label: "Knowledge", icon: CloudUpload },
  { label: "Configure", icon: Settings2 },
  { label: "Test", icon: Code2 },
  { label: "Deploy", icon: Rocket },
];

const modelDefaults = {
  gemini: "gemini-3.5-flash-lite",
  grok: "grok-4.7",
  openai: "gpt-4o-mini",
  claude: "claude-3-5-haiku-latest",
} as const;

type Provider = keyof typeof modelDefaults;
type Config = {
  provider: Provider;
  model: string;
  prompt: string;
  temperature: number;
  topK: number;
  reranker: boolean;
  calculator: boolean;
  webSearch: boolean;
  webhook: boolean;
  webhookName: string;
  webhookUrl: string;
};

function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: (value: boolean) => void; label: string; description: string }) {
  return <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl border bg-white p-4"><span><span className="block text-sm font-semibold">{label}</span><span className="mt-1 block text-xs leading-5 text-slate-500">{description}</span></span><input type="checkbox" className="peer sr-only" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span className="relative h-6 w-11 shrink-0 rounded-full bg-slate-200 transition peer-checked:bg-primary after:absolute after:left-1 after:top-1 after:size-4 after:rounded-full after:bg-white after:shadow after:transition peer-checked:after:translate-x-5" /></label>;
}

function CopyBlock({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() { await navigator.clipboard.writeText(value); setCopied(true); window.setTimeout(() => setCopied(false), 1500); }
  return <div><div className="mb-2 flex items-center justify-between"><Label>{label}</Label><button onClick={() => void copy()} className="text-xs font-semibold text-primary">{copied ? "Copied" : "Copy"}</button></div><div className="relative overflow-hidden rounded-xl bg-slate-950"><pre className="overflow-x-auto p-4 pr-12 text-xs leading-6 text-slate-200"><code>{value}</code></pre><button onClick={() => void copy()} className="absolute right-3 top-3 rounded-lg bg-white/10 p-2 text-white hover:bg-white/20" aria-label={`Copy ${label}`}>{copied ? <Check className="size-4" /> : <Clipboard className="size-4" />}</button></div></div>;
}

export function CreateAgentWizard() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState(0);
  const [maxStep, setMaxStep] = useState(0);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [apiKey, setApiKey] = useState<ApiKeyCreated | null>(null);
  const [origin, setOrigin] = useState("http://localhost:3000");
  const [originSaved, setOriginSaved] = useState(false);
  const [config, setConfig] = useState<Config>({
    provider: "gemini", model: modelDefaults.gemini,
    prompt: "Answer clearly using only the provided document context. Cite every factual claim.",
    temperature: 0.2, topK: 5, reranker: false,
    calculator: true, webSearch: false, webhook: false, webhookName: "", webhookUrl: "",
  });

  const loadDocuments = useCallback(async () => {
    if (!agentId) return;
    setDocuments(await api.listDocuments(agentId));
  }, [agentId]);

  useEffect(() => {
    if (!agentId || !documents.some((item) => ["pending", "processing"].includes(item.status))) return;
    const timer = window.setInterval(() => void loadDocuments(), 2500);
    return () => window.clearInterval(timer);
  }, [agentId, documents, loadDocuments]);

  function advance(next: number) { setStep(next); setMaxStep((current) => Math.max(current, next)); setError(""); }

  async function createAgent() {
    if (!name.trim() || !purpose.trim()) { setError("Add an agent name and a clear purpose."); return; }
    setBusy(true); setError("");
    try {
      const prompt = `${config.prompt}\n\nAgent purpose: ${purpose.trim()}`;
      const agent = await api.createAgent({
        name: name.trim(), system_prompt: prompt, llm_provider: config.provider,
        model: config.model, temperature: config.temperature, top_k: config.topK,
        use_reranker: config.reranker, allowed_origins: [origin], tools: [{ type: "calculator", enabled: true }],
      });
      setAgentId(agent.id); setConfig((current) => ({ ...current, prompt })); advance(1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create agent"); }
    finally { setBusy(false); }
  }

  async function upload(files: FileList | File[]) {
    if (!agentId) return;
    setBusy(true); setError("");
    const valid = Array.from(files).filter((file) => /\.(pdf|docx|txt|md|html?)$/i.test(file.name));
    if (!valid.length) { setError("Choose a PDF, DOCX, TXT, Markdown, or HTML file."); setBusy(false); return; }
    try { for (const file of valid) await api.uploadDocument(agentId, file); await loadDocuments(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Upload failed"); }
    finally { setBusy(false); if (fileInput.current) fileInput.current.value = ""; }
  }

  async function saveConfig() {
    if (!agentId) return;
    setBusy(true); setError("");
    const tools: Array<Record<string, unknown>> = [];
    if (config.calculator) tools.push({ type: "calculator", enabled: true });
    if (config.webSearch) tools.push({ type: "web_search", enabled: true });
    if (config.webhook) {
      if (!config.webhookName.trim() || !config.webhookUrl.startsWith("https://")) { setError("Webhook tools require a name and an HTTPS URL."); setBusy(false); return; }
      tools.push({ type: "webhook", name: config.webhookName, description: `Call ${config.webhookName}`, url: config.webhookUrl, enabled: true });
    }
    try {
      await api.updateAgent(agentId, { llm_provider: config.provider, model: config.model, system_prompt: config.prompt, temperature: config.temperature, top_k: config.topK, use_reranker: config.reranker, tools: tools as never });
      advance(3);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save configuration"); }
    finally { setBusy(false); }
  }

  async function createKey() {
    if (!agentId) return;
    setBusy(true); setError("");
    try { setApiKey(await api.createApiKey(agentId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to generate an API key"); }
    finally { setBusy(false); }
  }

  async function saveOrigin() {
    if (!agentId) return;
    try { await api.updateWidget(agentId, { greeting: `Hi! Ask ${name} a question.`, theme: { primary_color: "#7c3aed", position: "bottom-right" }, allowed_origins: [origin] }); setOriginSaved(true); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save origin"); }
  }

  const snippets = useMemo(() => {
    if (!agentId || !apiKey) return null;
    const backend = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const frontend = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const curl = `curl -X POST "${backend}/v1/agents/${agentId}/chat" \\\n  -H "Authorization: Bearer ${apiKey.key}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"message":"What is in my documents?","stream":false}'`;
    const python = `import requests\n\nresponse = requests.post(\n    "${backend}/v1/agents/${agentId}/chat",\n    headers={"Authorization": "Bearer ${apiKey.key}"},\n    json={"message": "What is in my documents?", "stream": False},\n)\nprint(response.json())`;
    const javascript = `const response = await fetch("${backend}/v1/agents/${agentId}/chat", {\n  method: "POST",\n  headers: {\n    "Authorization": "Bearer ${apiKey.key}",\n    "Content-Type": "application/json",\n  },\n  body: JSON.stringify({ message: "What is in my documents?", stream: false }),\n});\nconsole.log(await response.json());`;
    const widget = `<script src="${frontend}/widget.js" data-agent-id="${agentId}"></script>`;
    return { curl, python, javascript, widget };
  }, [agentId, apiKey]);

  return (
    <div>
      <div className="mb-8 flex items-center justify-between"><div><Link href="/dashboard/agents" className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-900"><ArrowLeft className="size-4" />Agents</Link><h1 className="mt-3 text-3xl font-bold tracking-tight">Create an agent</h1><p className="mt-1 text-sm text-slate-500">From knowledge to deployment in five guided steps.</p></div>{agentId && <Badge tone="primary">Draft · {name}</Badge>}</div>
      <div className="mb-8 grid grid-cols-5 gap-1 rounded-2xl border bg-white p-2 shadow-sm">{steps.map(({ label, icon: Icon }, index) => <button key={label} disabled={index > maxStep} onClick={() => index <= maxStep && setStep(index)} className={cn("focus-ring flex min-w-0 flex-col items-center gap-1.5 rounded-xl px-2 py-3 text-xs font-medium transition sm:flex-row sm:justify-center sm:text-sm", index === step ? "bg-slate-950 text-white" : index < step ? "text-emerald-600" : "text-slate-400", index <= maxStep && index !== step && "hover:bg-slate-50")}><span className="relative">{index < step ? <CheckCircle2 className="size-4" /> : <Icon className="size-4" />}</span><span className="hidden sm:inline">{label}</span></button>)}</div>
      {error && <p className="mb-5 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}

      {step === 0 && <Card className="mx-auto max-w-2xl p-6 sm:p-8"><p className="text-xs font-semibold uppercase tracking-[.18em] text-primary">Step 1 of 5</p><h2 className="mt-2 text-2xl font-bold">What should your agent do?</h2><p className="mt-2 text-sm text-slate-500">Give it a memorable name and describe the questions it should answer.</p><div className="mt-7 space-y-5"><div className="space-y-2"><Label htmlFor="agent-name">Agent name</Label><Input id="agent-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Customer Support Copilot" maxLength={120} /></div><div className="space-y-2"><Label htmlFor="purpose">Purpose</Label><Textarea id="purpose" value={purpose} onChange={(event) => setPurpose(event.target.value)} placeholder="Answer product and policy questions using our support documentation." /><p className="text-xs text-slate-400">This becomes part of the system prompt and can be refined later.</p></div></div><div className="mt-8 flex justify-end"><Button onClick={() => void createAgent()} disabled={busy}>{busy && <Loader2 className="mr-2 size-4 animate-spin" />}Create and continue <ArrowRight className="ml-2 size-4" /></Button></div></Card>}

      {step === 1 && <div className="mx-auto max-w-3xl"><Card className="p-6 sm:p-8"><p className="text-xs font-semibold uppercase tracking-[.18em] text-primary">Step 2 of 5</p><h2 className="mt-2 text-2xl font-bold">Add your knowledge</h2><p className="mt-2 text-sm text-slate-500">Files begin ingesting immediately. You can continue while processing runs.</p><input ref={fileInput} className="hidden" type="file" multiple accept=".pdf,.docx,.txt,.md,.html,.htm" onChange={(event) => event.target.files && void upload(event.target.files)} /><button onClick={() => fileInput.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); void upload(event.dataTransfer.files); }} className="focus-ring mt-7 w-full rounded-2xl border-2 border-dashed border-slate-200 px-6 py-10 text-center transition hover:border-violet-300 hover:bg-violet-50/30"><CloudUpload className="mx-auto size-8 text-primary" /><span className="mt-3 block font-semibold">Drop files or click to browse</span><span className="mt-1 block text-xs text-slate-400">PDF, DOCX, TXT, MD, HTML · server size limits apply</span>{busy && <Loader2 className="mx-auto mt-4 size-5 animate-spin text-primary" />}</button>{documents.length > 0 && <div className="mt-6 divide-y rounded-xl border">{documents.map((document) => <div key={document.id} className="flex items-center gap-3 px-4 py-3"><FileText className="size-4 text-slate-400" /><span className="min-w-0 flex-1 truncate text-sm font-medium">{document.filename}</span><Badge tone={document.status === "ready" ? "success" : document.status === "failed" ? "danger" : "warning"} className="capitalize">{["pending", "processing"].includes(document.status) && <Loader2 className="mr-1 size-3 animate-spin" />}{document.status}</Badge></div>)}</div>}</Card><div className="mt-5 flex justify-between"><Button variant="outline" onClick={() => setStep(0)}><ArrowLeft className="mr-2 size-4" />Back</Button><Button onClick={() => advance(2)}>Configure agent <ArrowRight className="ml-2 size-4" /></Button></div></div>}

      {step === 2 && <div className="mx-auto max-w-4xl"><Card className="p-6 sm:p-8"><p className="text-xs font-semibold uppercase tracking-[.18em] text-primary">Step 3 of 5</p><h2 className="mt-2 text-2xl font-bold">Tune its behavior</h2><div className="mt-7 grid gap-6 md:grid-cols-2"><div className="space-y-2"><Label>Provider</Label><select className="focus-ring h-11 w-full rounded-xl border bg-white px-3 text-sm" value={config.provider} onChange={(event) => { const provider = event.target.value as Provider; setConfig({ ...config, provider, model: modelDefaults[provider] }); }}>{Object.keys(modelDefaults).map((provider) => <option key={provider} value={provider}>{provider[0].toUpperCase() + provider.slice(1)}</option>)}</select></div><div className="space-y-2"><Label>Model</Label><Input value={config.model} onChange={(event) => setConfig({ ...config, model: event.target.value })} /></div><div className="space-y-2 md:col-span-2"><Label>System prompt</Label><Textarea className="min-h-36" value={config.prompt} onChange={(event) => setConfig({ ...config, prompt: event.target.value })} /></div><div className="space-y-2"><div className="flex justify-between"><Label>Temperature</Label><span className="text-sm font-semibold">{config.temperature}</span></div><input className="w-full accent-violet-600" type="range" min="0" max="1" step="0.1" value={config.temperature} onChange={(event) => setConfig({ ...config, temperature: Number(event.target.value) })} /></div><div className="space-y-2"><Label>Retrieved chunks (top_k)</Label><Input type="number" min={1} max={100} value={config.topK} onChange={(event) => setConfig({ ...config, topK: Number(event.target.value) })} /></div><div className="md:col-span-2"><Toggle checked={config.reranker} onChange={(reranker) => setConfig({ ...config, reranker })} label="Cohere reranker" description="Improve result ordering when a Cohere key is configured." /></div></div><h3 className="mt-8 font-semibold">Optional tools</h3><div className="mt-3 grid gap-3 md:grid-cols-3"><Toggle checked={config.calculator} onChange={(calculator) => setConfig({ ...config, calculator })} label="Calculator" description="Evaluate numeric expressions." /><Toggle checked={config.webSearch} onChange={(webSearch) => setConfig({ ...config, webSearch })} label="Web search" description="Use configured search service." /><Toggle checked={config.webhook} onChange={(webhook) => setConfig({ ...config, webhook })} label="Webhook" description="Call your HTTPS endpoint." /></div>{config.webhook && <div className="mt-4 grid gap-4 rounded-xl bg-slate-50 p-4 md:grid-cols-2"><div className="space-y-2"><Label>Tool name</Label><Input value={config.webhookName} onChange={(event) => setConfig({ ...config, webhookName: event.target.value })} placeholder="Check order status" /></div><div className="space-y-2"><Label>HTTPS URL</Label><Input value={config.webhookUrl} onChange={(event) => setConfig({ ...config, webhookUrl: event.target.value })} placeholder="https://api.example.com/tool" /></div></div>}</Card><div className="mt-5 flex justify-between"><Button variant="outline" onClick={() => setStep(1)}><ArrowLeft className="mr-2 size-4" />Back</Button><Button onClick={() => void saveConfig()} disabled={busy}>{busy && <Loader2 className="mr-2 size-4 animate-spin" />}Save and test <ArrowRight className="ml-2 size-4" /></Button></div></div>}

      {step === 3 && agentId && <div><div className="mb-5 flex items-end justify-between"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-primary">Step 4 of 5</p><h2 className="mt-2 text-2xl font-bold">Verify grounded answers</h2></div><Button onClick={() => advance(4)}>Deploy <ArrowRight className="ml-2 size-4" /></Button></div><ChatPlayground agentId={agentId} title={`Chat with ${name}`} /></div>}

      {step === 4 && agentId && <div className="mx-auto max-w-5xl"><div className="mb-6"><p className="text-xs font-semibold uppercase tracking-[.18em] text-primary">Step 5 of 5</p><h2 className="mt-2 text-2xl font-bold">Ship your agent</h2><p className="mt-2 text-sm text-slate-500">Create a server key or embed the browser-safe widget.</p></div>{!apiKey ? <Card className="p-8 text-center"><span className="mx-auto grid size-12 place-items-center rounded-2xl bg-violet-50 text-primary"><KeyRound className="size-6" /></span><h3 className="mt-4 text-lg font-semibold">Generate your first API key</h3><p className="mt-2 text-sm text-slate-500">The full value is displayed once. Store it in a secret manager.</p><Button className="mt-5" onClick={() => void createKey()} disabled={busy}>{busy && <Loader2 className="mr-2 size-4 animate-spin" />}Generate API key</Button></Card> : <div className="space-y-6"><Card className="border-emerald-200 bg-emerald-50/70 p-5"><div className="flex items-center gap-2 text-emerald-800"><CheckCircle2 className="size-5" /><h3 className="font-semibold">API key created — copy it now</h3></div><code className="mt-4 block overflow-x-auto rounded-xl bg-white p-4 text-sm ring-1 ring-emerald-200">{apiKey.key}</code></Card><div className="grid gap-6 lg:grid-cols-2"><CopyBlock label="cURL" value={snippets?.curl ?? ""} /><CopyBlock label="Python" value={snippets?.python ?? ""} /><CopyBlock label="JavaScript" value={snippets?.javascript ?? ""} /><div><div className="mb-2 flex items-center justify-between"><Label>Allowed website origin</Label>{originSaved && <span className="text-xs font-semibold text-emerald-600">Saved</span>}</div><div className="flex gap-2"><Input value={origin} onChange={(event) => { setOrigin(event.target.value); setOriginSaved(false); }} /><Button variant="outline" onClick={() => void saveOrigin()}>Save</Button></div><div className="mt-4"><CopyBlock label="Widget embed" value={snippets?.widget ?? ""} /></div></div></div></div>}<div className="mt-8 flex justify-between"><Button variant="outline" onClick={() => setStep(3)}><ArrowLeft className="mr-2 size-4" />Back</Button><Button asChild><Link href={`/dashboard/agents/${agentId}`}>Finish <Check className="ml-2 size-4" /></Link></Button></div></div>}
    </div>
  );
}

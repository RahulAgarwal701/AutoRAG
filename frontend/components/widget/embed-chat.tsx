"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { ArrowUp, Bot, ExternalLink, FileText, Loader2, X } from "lucide-react";

type Citation = { document: string; page?: number | null; snippet: string; link: string };
type Message = { id: string; role: "user" | "assistant"; content: string; citations?: Citation[] };
type WidgetConfig = { name: string; greeting: string; theme: Record<string, unknown> };
type InitMessage = {
  type: "autorag:init";
  agentId: string;
  parentOrigin: string;
  token: string;
  expiresIn: number;
  config: WidgetConfig;
};

function streamError(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return "The agent could not complete this request.";
}

function parseEvent(block: string): { event: string; data: unknown } | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!data.length) return null;
  try { return { event, data: JSON.parse(data.join("\n")) }; }
  catch { return { event, data: data.join("\n") }; }
}

function safeColor(value: unknown): string {
  return typeof value === "string" && /^(#[0-9a-f]{3,8}|rgb\(|hsl\()/i.test(value)
    ? value
    : "#7c3aed";
}

export function EmbedChat({ agentId }: { agentId: string }) {
  const [config, setConfig] = useState<WidgetConfig | null>(null);
  const [parentOrigin, setParentOrigin] = useState("");
  const [token, setToken] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const parentWindow = useRef<Window | null>(null);
  const parentOriginRef = useRef("");
  const messageList = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  const primary = safeColor(config?.theme?.primary_color);
  const storageKey = useMemo(
    () => parentOrigin ? `autorag:${agentId}:${parentOrigin}` : "",
    [agentId, parentOrigin],
  );

  const persist = useCallback((nextMessages: Message[], nextSessionId: string | null) => {
    if (!storageKey) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify({ messages: nextMessages.slice(-40), sessionId: nextSessionId }));
    } catch { /* Third-party storage can be unavailable. */ }
  }, [storageKey]);

  useEffect(() => {
    function receive(event: MessageEvent) {
      const payload = event.data as { type?: string; message?: string } | null;
      if (!payload || payload.type !== "autorag:init") {
        if (event.source !== window.parent || event.origin !== parentOriginRef.current) return;
        if (payload?.type === "autorag:error") setError(payload.message ?? "Unable to refresh chat");
        if (payload?.type === "autorag:open") input.current?.focus();
        return;
      }
      const init = payload as unknown as InitMessage;
      if (init.agentId !== agentId || init.parentOrigin !== event.origin || event.source !== window.parent) return;
      parentWindow.current = window.parent;
      parentOriginRef.current = event.origin;
      setParentOrigin(event.origin);
      setToken(init.token);
      setConfig(init.config);
      setError("");
    }
    window.addEventListener("message", receive);
    window.parent.postMessage({ type: "autorag:ready" }, "*");
    return () => window.removeEventListener("message", receive);
  }, [agentId]);

  useEffect(() => {
    if (!storageKey || !config) return;
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) ?? "null") as { messages?: Message[]; sessionId?: string } | null;
      if (stored?.messages?.length) setMessages(stored.messages);
      else setMessages([{ id: crypto.randomUUID(), role: "assistant", content: config.greeting }]);
      setSessionId(stored?.sessionId ?? null);
    } catch {
      setMessages([{ id: crypto.randomUUID(), role: "assistant", content: config.greeting }]);
    }
  }, [config, storageKey]);

  useEffect(() => {
    messageList.current?.scrollTo({ top: messageList.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (config && parentOrigin) post("autorag:resize", { width: 380, height: 620 });
  // post is intentionally derived from the current parent handshake.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, parentOrigin]);

  function post(type: string, data: Record<string, unknown> = {}) {
    if (!parentOrigin || !parentWindow.current) return;
    parentWindow.current.postMessage({ type, ...data }, parentOrigin);
  }

  async function send(message: string) {
    if (!token || loading) return;
    const assistantId = crypto.randomUUID();
    const user: Message = { id: crypto.randomUUID(), role: "user", content: message };
    setMessages((current) => [...current, user, { id: assistantId, role: "assistant", content: "", citations: [] }]);
    setLoading(true); setError("");
    let nextSessionId = sessionId;
    try {
      const response = await fetch(`/api/widget/${encodeURIComponent(agentId)}/chat`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "X-AutoRAG-Parent-Origin": parentOrigin,
        },
        body: JSON.stringify({ message, session_id: sessionId, stream: true }),
      });
      if (response.status === 401) {
        setMessages((current) => current.filter((item) => item.id !== assistantId));
        post("autorag:refresh-session");
        throw new Error("Your secure session was refreshed. Please send the message again.");
      }
      if (!response.ok || !response.body) throw new Error("The agent could not answer right now.");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const parsed = parseEvent(block);
          if (!parsed) continue;
          if (parsed.event === "session") {
            nextSessionId = (parsed.data as { session_id: string }).session_id;
            setSessionId(nextSessionId);
          }
          if (parsed.event === "token") {
            const text = (parsed.data as { text: string }).text;
            setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: item.content + text } : item));
          }
          if (parsed.event === "citations") {
            setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, citations: parsed.data as Citation[] } : item));
          }
          if (parsed.event === "error") throw new Error(streamError(parsed.data));
        }
        if (done) break;
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to send message");
      setMessages((current) => current.filter((item) => item.id !== assistantId));
    } finally {
      setLoading(false);
      setMessages((current) => { persist(current, nextSessionId); return current; });
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const message = question.trim();
    if (!message) return;
    setQuestion("");
    void send(message);
  }

  if (!config) {
    return <main className="grid min-h-screen place-items-center bg-white"><Loader2 className="size-6 animate-spin text-violet-600" /></main>;
  }

  return (
    <main className="relative flex h-screen flex-col overflow-hidden bg-white text-slate-900" style={{ "--widget-primary": primary } as CSSProperties}>
      <header className="flex items-center justify-between px-4 py-3.5 text-white" style={{ background: primary }}>
        <div className="flex min-w-0 items-center gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-xl bg-white/15"><Bot className="size-5" /></span><div className="min-w-0"><h1 className="truncate text-sm font-bold">{config.name}</h1><p className="text-[11px] text-white/70">Grounded in your documents</p></div></div>
        <button type="button" onClick={() => post("autorag:close")} className="rounded-lg p-2 transition hover:bg-white/15" aria-label="Close chat"><X className="size-4" /></button>
      </header>
      <div ref={messageList} className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-4">
        {messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[86%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-5 shadow-sm ${message.role === "user" ? "text-white" : "border bg-white text-slate-700"}`} style={message.role === "user" ? { background: primary } : undefined}>
              {message.content || <Loader2 className="size-4 animate-spin" />}
              {!!message.citations?.length && <div className="mt-2 flex flex-wrap gap-1.5 border-t border-slate-200/70 pt-2">{message.citations.map((citation, index) => <button key={`${citation.document}-${index}`} type="button" onClick={() => setActiveCitation(citation)} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600 hover:bg-slate-200">[{index + 1}]</button>)}</div>}
            </div>
          </div>
        ))}
      </div>
      {error && <div className="border-t border-rose-100 bg-rose-50 px-4 py-2 text-xs text-rose-700">{error}</div>}
      <form onSubmit={submit} className="flex items-center gap-2 border-t bg-white p-3">
        <input ref={input} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question…" className="h-11 min-w-0 flex-1 rounded-xl border border-slate-200 px-3 text-sm outline-none focus:ring-2" style={{ caretColor: primary }} aria-label="Message" />
        <button disabled={loading || !question.trim()} className="grid size-11 shrink-0 place-items-center rounded-xl text-white disabled:opacity-50" style={{ background: primary }} aria-label="Send"><ArrowUp className="size-4" /></button>
      </form>
      {activeCitation && <div className="absolute inset-0 z-20 flex items-end bg-slate-950/20 p-3" onClick={() => setActiveCitation(null)}><section className="w-full rounded-2xl border bg-white p-4 shadow-2xl" onClick={(event) => event.stopPropagation()}><div className="flex items-start justify-between gap-3"><span className="grid size-9 place-items-center rounded-xl bg-violet-50 text-violet-600"><FileText className="size-4" /></span><button onClick={() => setActiveCitation(null)} className="rounded-lg p-1.5 hover:bg-slate-100" aria-label="Close citation"><X className="size-4" /></button></div><h2 className="mt-3 truncate text-sm font-bold">{activeCitation.document}</h2><p className="mt-1 text-[11px] text-slate-400">{activeCitation.page ? `Page ${activeCitation.page}` : "Source document"}</p><p className="mt-3 max-h-28 overflow-y-auto text-xs leading-5 text-slate-600">{activeCitation.snippet}</p><a href={activeCitation.link} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold" style={{ color: primary }}>Open source <ExternalLink className="size-3" /></a></section></div>}
    </main>
  );
}

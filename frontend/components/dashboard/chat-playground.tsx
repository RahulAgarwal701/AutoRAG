"use client";

import { useRef, useState, type FormEvent } from "react";
import { ArrowUp, Bot, ExternalLink, FileText, Loader2, RotateCcw, User } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

type Citation = { document: string; page?: number | null; snippet: string; link: string };
type ChatMessage = { id: string; role: "user" | "assistant"; content: string; citations?: Citation[] };

function streamError(data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
  }
  return "The agent could not complete this request";
}

function parseBlock(block: string): { event: string; data: unknown } | null {
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

export function ChatPlayground({ agentId, title = "Test your agent" }: { agentId: string; title?: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const assistantId = useRef("");
  const activeCitations = messages.filter((message) => message.role === "assistant").at(-1)?.citations ?? [];

  async function submit(event: FormEvent) {
    event.preventDefault();
    const message = question.trim();
    if (!message || loading) return;
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: message };
    assistantId.current = crypto.randomUUID();
    setMessages((current) => [...current, userMessage, { id: assistantId.current, role: "assistant", content: "", citations: [] }]);
    setQuestion(""); setLoading(true); setError("");
    try {
      const response = await fetch(`/api/backend/api/v1/agents/${agentId}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      if (!response.ok || !response.body) throw new Error("The chat service is unavailable");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const parsed = parseBlock(block);
          if (!parsed) continue;
          if (parsed.event === "session") setSessionId((parsed.data as { session_id: string }).session_id);
          if (parsed.event === "token") {
            const text = (parsed.data as { text: string }).text;
            setMessages((current) => current.map((item) => item.id === assistantId.current ? { ...item, content: item.content + text } : item));
          }
          if (parsed.event === "citations") {
            setMessages((current) => current.map((item) => item.id === assistantId.current ? { ...item, citations: parsed.data as Citation[] } : item));
          }
          if (parsed.event === "error") throw new Error(streamError(parsed.data));
        }
        if (done) break;
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to send message");
      setMessages((current) => current.filter((item) => item.id !== assistantId.current));
    } finally { setLoading(false); }
  }

  function reset() { setMessages([]); setSessionId(null); setError(""); }

  return (
    <div className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
      <Card className="flex min-h-[620px] flex-col overflow-hidden">
        <div className="flex items-center justify-between border-b px-5 py-4"><div><h2 className="font-semibold">{title}</h2><p className="mt-0.5 text-xs text-slate-400">Streaming, memory, and grounded citations</p></div><Button size="sm" variant="ghost" onClick={reset}><RotateCcw className="mr-2 size-3.5" />Reset</Button></div>
        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          {!messages.length && <div className="grid min-h-80 place-items-center text-center"><div><span className="mx-auto grid size-12 place-items-center rounded-2xl bg-violet-50 text-primary"><Bot className="size-6" /></span><h3 className="mt-4 font-semibold">Ask about your documents</h3><p className="mt-1 max-w-sm text-sm text-slate-500">Try a specific question whose answer appears in an uploaded source.</p></div></div>}
          {messages.map((message) => <div key={message.id} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>{message.role === "assistant" && <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-slate-950 text-white"><Bot className="size-4" /></span>}<div className={`max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "bg-primary text-white" : "bg-slate-100 text-slate-700"}`}>{message.content || <Loader2 className="size-4 animate-spin" />}{message.citations?.length ? <div className="mt-2 flex flex-wrap gap-1.5">{message.citations.map((_, index) => <Badge key={index} className="bg-white">[{index + 1}]</Badge>)}</div> : null}</div>{message.role === "user" && <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-violet-100 text-violet-700"><User className="size-4" /></span>}</div>)}
        </div>
        <form onSubmit={submit} className="border-t bg-white p-4"><div className="flex items-end gap-2"><Textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Ask a question…" className="min-h-12 max-h-32 resize-none py-3" /><Button size="icon" className="size-12 shrink-0" disabled={loading || !question.trim()} aria-label="Send"><ArrowUp className="size-4" /></Button></div>{error && <p className="mt-2 text-xs text-rose-600">{error}</p>}</form>
      </Card>
      <Card className="min-h-72 overflow-hidden"><div className="border-b px-5 py-4"><h2 className="font-semibold">Sources</h2><p className="mt-0.5 text-xs text-slate-400">Citations from the latest answer</p></div><div className="space-y-3 p-4">{!activeCitations.length ? <div className="py-16 text-center"><FileText className="mx-auto size-7 text-slate-300" /><p className="mt-3 text-sm text-slate-400">Sources appear here after an answer.</p></div> : activeCitations.map((citation, index) => <a key={`${citation.document}-${index}`} href={citation.link} target="_blank" rel="noreferrer" className="block rounded-xl border bg-white p-4 transition hover:border-violet-200 hover:shadow-sm"><div className="flex items-start justify-between gap-3"><Badge tone="primary">[{index + 1}]</Badge><ExternalLink className="size-3.5 text-slate-400" /></div><p className="mt-3 truncate text-sm font-semibold">{citation.document}</p><p className="mt-1 text-xs text-slate-400">{citation.page ? `Page ${citation.page}` : "Source document"}</p><p className="mt-3 line-clamp-4 text-xs leading-5 text-slate-500">{citation.snippet}</p></a>)}</div></Card>
    </div>
  );
}

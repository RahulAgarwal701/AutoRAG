"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, FileText, Loader2, RefreshCw, Trash2, UploadCloud } from "lucide-react";

import { PageHeader } from "@/components/dashboard/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, type Document } from "@/lib/api/client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const statusTone = { pending: "warning", processing: "primary", ready: "success", failed: "danger" } as const;

export function DocumentManager({ agentId }: { agentId: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setDocuments(await api.listDocuments(agentId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load documents"); }
  }, [agentId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!documents.some((document) => ["pending", "processing"].includes(document.status))) return;
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [documents, load]);

  async function upload(files: FileList | File[]) {
    setUploading(true); setError("");
    const supported = Array.from(files).filter((file) => /\.(pdf|docx|txt|md|html?)$/i.test(file.name));
    if (supported.length !== files.length) setError("Some files were skipped. Use PDF, DOCX, TXT, MD, or HTML.");
    try {
      for (const file of supported) await api.uploadDocument(agentId, file);
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Upload failed"); }
    finally { setUploading(false); if (input.current) input.current.value = ""; }
  }

  async function view(document: Document) {
    try { window.open((await api.documentUrl(agentId, document.id)).url, "_blank", "noopener,noreferrer"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to open document"); }
  }

  async function remove(document: Document) {
    if (!window.confirm(`Delete ${document.filename}? This also removes its vectors.`)) return;
    try { await api.deleteDocument(agentId, document.id); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Delete failed"); }
  }

  return (
    <>
      <PageHeader title="Documents" description="Upload the knowledge your agent can search and cite." action={<Button variant="outline" onClick={() => void load()}><RefreshCw className="mr-2 size-4" />Refresh</Button>} />
      <Card
        className={cn("border-2 border-dashed p-8 text-center transition", dragging && "border-primary bg-violet-50/60")}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files); }}
      >
        <input ref={input} type="file" multiple accept=".pdf,.docx,.txt,.md,.html,.htm" className="hidden" onChange={(event) => event.target.files && void upload(event.target.files)} />
        <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-violet-50 text-primary"><UploadCloud className="size-6" /></span>
        <h2 className="mt-4 font-semibold">Drop documents here</h2>
        <p className="mt-1 text-sm text-slate-500">PDF, DOCX, TXT, Markdown, or HTML</p>
        <Button className="mt-5" variant="outline" onClick={() => input.current?.click()} disabled={uploading}>
          {uploading && <Loader2 className="mr-2 size-4 animate-spin" />}Choose files
        </Button>
      </Card>
      {error && <p className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <Card className="mt-6 overflow-hidden">
        <div className="border-b px-5 py-4"><h2 className="font-semibold">Knowledge sources <span className="ml-1 text-slate-400">({documents.length})</span></h2></div>
        {!documents.length ? (
          <div className="px-6 py-14 text-center text-sm text-slate-500">No documents uploaded yet.</div>
        ) : (
          <div className="divide-y">
            {documents.map((document) => (
              <div key={document.id} className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center">
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-500"><FileText className="size-5" /></span>
                <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{document.filename}</p><p className="mt-1 text-xs text-slate-400">{formatDate(document.created_at)} · {document.chunk_count} chunks</p>{document.error && <p className="mt-1 text-xs text-rose-600">{document.error}</p>}</div>
                <Badge tone={statusTone[document.status]} className="w-fit capitalize">{document.status === "processing" && <Loader2 className="mr-1.5 size-3 animate-spin" />}{document.status}</Badge>
                <div className="flex gap-1">
                  <Button size="icon" variant="ghost" onClick={() => void view(document)} aria-label="View source"><ExternalLink className="size-4" /></Button>
                  <Button size="icon" variant="ghost" onClick={() => void remove(document)} aria-label="Delete document" className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"><Trash2 className="size-4" /></Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

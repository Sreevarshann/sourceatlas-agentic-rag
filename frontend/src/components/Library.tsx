"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, CheckCircle2, FileText, Globe, Library as LibIcon, Loader2, RefreshCw, Search, Trash2, Upload, X } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Doc } from "@/lib/types";
import { Button, Card, Chip, Empty, ErrorNote, Skeleton } from "./ui";

export function Library() {
  const [collection, setCollection] = useState<string>("");
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");
  const collections = useQuery({ queryKey: ["collections"], queryFn: api.collections });
  const docs = useQuery({
    queryKey: ["documents", collection, q, tag],
    queryFn: () => api.documents({ collection, q, tag }),
    refetchInterval: (query) => ((query.state.data ?? []).some((d) => d.status === "pending" || d.status === "processing") ? 1500 : false),
  });
  const tags = [...new Set((docs.data ?? []).flatMap((d) => d.tags))].sort();
  return (
    <div className="mx-auto grid max-w-[1500px] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[240px_1fr]">
      <aside className="flex flex-col gap-4">
        <div className="flex gap-2"><UploadDialog /><UrlDialog /></div>
        <nav aria-label="Collections" className="flex flex-col gap-0.5">
          <p className="px-3 pb-1 text-[11px] uppercase tracking-widest text-muted">Collections</p>
          {[{ id: "", name: "All sources", document_count: (collections.data ?? []).reduce((n, c) => n + c.document_count, 0) }, ...(collections.data ?? [])].map((c) => (
            <button key={c.id} onClick={() => setCollection(c.name === "All sources" ? "" : c.name)} aria-current={(c.name === "All sources" ? "" : c.name) === collection} className={cn("flex items-center justify-between rounded-xl px-3 py-2 text-left text-sm", (c.name === "All sources" ? "" : c.name) === collection ? "bg-indigo-soft text-indigo" : "hover:bg-paper-2")}>
              <span className="flex items-center gap-2"><LibIcon className="size-3.5" aria-hidden />{c.name}</span>
              <span className="text-xs text-muted">{c.document_count}</span>
            </button>
          ))}
        </nav>
        {tags.length > 0 && (
          <div>
            <p className="px-3 pb-1 text-[11px] uppercase tracking-widest text-muted">Tags</p>
            <div className="flex flex-wrap gap-1.5 px-2">
              {tags.map((t) => <button key={t} onClick={() => setTag(tag === t ? "" : t)} aria-pressed={tag === t}><Chip tone={tag === t ? "teal" : "neutral"}>#{t}</Chip></button>)}
            </div>
          </div>
        )}
      </aside>
      <section className="min-w-0">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-serif text-3xl tracking-tight">Knowledge Library</h1>
            <p className="mt-1 text-sm text-muted">Documents are extracted with page and section provenance, chunked, embedded and indexed for hybrid search.</p>
          </div>
          <label className="relative w-full max-w-xs">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles" aria-label="Search documents" className="w-full rounded-full border border-line bg-paper py-2 pl-9 pr-4 text-sm outline-none focus:border-teal" />
          </label>
        </div>
        <div className="mt-6 grid gap-3">
          {docs.isLoading && Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-20" />)}
          {docs.isError && <ErrorNote error={docs.error} onRetry={() => docs.refetch()} />}
          {docs.data?.length === 0 && <Empty icon={<BookOpen className="size-5" />} title="The shelves are empty" action={<code className="rounded bg-paper-2 px-2 py-1 text-xs">make seed</code>}>Upload PDFs, Word documents, Markdown, HTML or text — or load the synthetic Halcyon Devices library.</Empty>}
          {docs.data?.map((d, i) => <DocRow key={d.id} d={d} i={i} />)}
        </div>
      </section>
    </div>
  );
}

function StatusChip({ d }: { d: Doc }) {
  if (d.status === "ready") return <Chip tone="teal"><CheckCircle2 className="size-3" /> indexed · {d.current?.passage_count} passages</Chip>;
  if (d.status === "failed") return <Chip tone="rose" title={d.current?.error ?? ""}><AlertTriangle className="size-3" /> failed</Chip>;
  return <Chip tone="sand"><Loader2 className="size-3 animate-spin" /> {d.status}</Chip>;
}

function DocRow({ d, i }: { d: Doc; i: number }) {
  const qc = useQueryClient();
  const reindex = useMutation({ mutationFn: () => api.reindex(d.id), onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }) });
  const remove = useMutation({ mutationFn: () => api.remove(d.id), onSuccess: () => (qc.invalidateQueries({ queryKey: ["documents"] }), qc.invalidateQueries({ queryKey: ["collections"] })) });
  const eff = d.meta.effective_date as string | undefined;
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 10) * 0.03 }}>
      <Card className="flex flex-wrap items-center gap-4 p-4">
        <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-indigo-soft text-indigo">{d.source_type === "web" ? <Globe className="size-5" /> : <FileText className="size-5" />}</div>
        <div className="min-w-0 flex-1">
          <Link href={`/documents/${d.id}`} className="font-serif text-lg hover:text-indigo">{d.title}</Link>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
            <span>{d.collection}</span>
            <span>{d.current?.filename}</span>
            <span>v{d.current?.version}{d.versions.length > 1 && ` of ${d.versions.length}`}</span>
            {d.current?.page_count && <span>{d.current.page_count} pages</span>}
            {eff && <span>effective {eff}</span>}
            {d.meta.synthetic === true && <Chip tone="sand">synthetic</Chip>}
            {d.tags.map((t) => <span key={t}>#{t}</span>)}
          </p>
        </div>
        <StatusChip d={d} />
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={() => reindex.mutate()} disabled={reindex.isPending} aria-label={`Reindex ${d.title}`}><RefreshCw className={cn("size-3.5", reindex.isPending && "animate-spin")} /></Button>
          <Button size="sm" variant="ghost" onClick={() => confirm(`Delete “${d.title}” and all versions? This cannot be undone.`) && remove.mutate()} aria-label={`Delete ${d.title}`}><Trash2 className="size-3.5 text-rose" /></Button>
        </div>
      </Card>
    </motion.div>
  );
}

function Modal({ trigger, title, children, open, setOpen }: { trigger: React.ReactNode; title: string; children: React.ReactNode; open: boolean; setOpen: (o: boolean) => void }) {
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/30 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,500px)] -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-line bg-paper p-6 shadow-2xl">
          <div className="flex items-start justify-between"><Dialog.Title className="font-serif text-2xl">{title}</Dialog.Title><Dialog.Close aria-label="Close" className="rounded-full p-1 hover:bg-paper-2"><X className="size-4" /></Dialog.Close></div>
          <Dialog.Description className="sr-only">{title}</Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const field = "mt-1 w-full rounded-xl border border-line bg-bg px-3 py-2 text-sm outline-none focus:border-teal";

function UploadDialog() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: (fd: FormData) => api.upload(fd),
    onSuccess: () => (setOpen(false), qc.invalidateQueries({ queryKey: ["documents"] }), qc.invalidateQueries({ queryKey: ["collections"] })),
  });
  return (
    <Modal open={open} setOpen={setOpen} title="Add a document" trigger={<Button variant="primary" size="sm" className="flex-1"><Upload className="size-3.5" /> Upload</Button>}>
      <form
        className="mt-4 flex flex-col gap-3 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const meta: Record<string, string> = {};
          for (const k of ["effective_date", "policy"]) if (f.get(k)) meta[k] = String(f.get(k));
          f.delete("effective_date");
          f.delete("policy");
          f.set("meta", JSON.stringify(meta));
          m.mutate(f);
        }}
      >
        <label>File <span className="text-muted">(PDF, DOCX, MD, TXT, HTML · 25 MB)</span><input name="file" type="file" required accept=".pdf,.docx,.md,.markdown,.txt,.html,.htm" className={field} aria-label="Document file" /></label>
        <div className="grid grid-cols-2 gap-3">
          <label>Collection<input name="collection" defaultValue="General" required maxLength={120} className={field} /></label>
          <label>Title<input name="title" maxLength={300} className={field} placeholder="from document" /></label>
          <label>Policy id<input name="policy" className={field} placeholder="e.g. returns" /></label>
          <label>Effective date<input name="effective_date" type="date" className={field} /></label>
        </div>
        <label>Tags<input name="tags" className={field} placeholder="comma separated" /></label>
        <p className="text-xs text-muted">Documents sharing a policy id are compared for conflicting statements; the effective date decides which is newer.</p>
        {m.isError && <p role="alert" className="text-rose">{(m.error as Error).message}</p>}
        <Button variant="primary" type="submit" disabled={m.isPending}>{m.isPending && <Loader2 className="size-4 animate-spin" />} Add to library</Button>
      </form>
    </Modal>
  );
}

function UrlDialog() {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const qc = useQueryClient();
  const m = useMutation({ mutationFn: () => api.ingestUrl(url, "Web"), onSuccess: () => (setOpen(false), setUrl(""), qc.invalidateQueries({ queryKey: ["documents"] })) });
  return (
    <Modal open={open} setOpen={setOpen} title="Ingest a public web page" trigger={<Button size="sm" aria-label="Ingest a web page"><Globe className="size-3.5" /></Button>}>
      <form className="mt-4 flex flex-col gap-3 text-sm" onSubmit={(e) => (e.preventDefault(), m.mutate())}>
        <label>URL<input value={url} onChange={(e) => setUrl(e.target.value)} type="url" required placeholder="https://…" className={field} /></label>
        <p className="text-xs text-muted">Only public http(s) pages are fetched (private, loopback and metadata addresses are blocked; redirects are re-checked). Web text is treated as untrusted evidence.</p>
        {m.isError && <p role="alert" className="text-rose">{(m.error as Error).message}</p>}
        <Button variant="primary" type="submit" disabled={m.isPending}>{m.isPending && <Loader2 className="size-4 animate-spin" />} Fetch & index</Button>
      </form>
    </Modal>
  );
}

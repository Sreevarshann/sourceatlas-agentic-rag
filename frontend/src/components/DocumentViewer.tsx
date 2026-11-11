"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, FileText } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { PdfPage } from "./PdfPage";
import { Card, Chip, ErrorNote, Skeleton } from "./ui";

export function DocumentViewer({ id }: { id: string }) {
  const params = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const passageId = params.get("passage");
  const versionParam = params.get("version");
  const doc = useQuery({ queryKey: ["document", id], queryFn: () => api.document(id) });
  const version = versionParam ? Number(versionParam) : doc.data?.current?.version;
  const passages = useQuery({ queryKey: ["passages", id, version], queryFn: () => api.passages(id, version), enabled: !!version });
  const selected = passages.data?.find((p) => p.id === passageId) ?? null;
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => ref.current?.scrollIntoView({ block: "center", behavior: "smooth" }), [selected?.id]);

  if (doc.isError) return <div className="p-6"><ErrorNote error={doc.error} /></div>;
  if (!doc.data) return <div className="p-6"><Skeleton className="h-96" /></div>;
  const d = doc.data;
  const ver = d.versions.find((v) => v.version === version) ?? d.current;
  const isPdf = ver?.mime === "application/pdf";
  const page = selected?.page ?? passages.data?.[0]?.page ?? 1;
  const select = (pid: string) => router.replace(`${path}?passage=${pid}${versionParam ? `&version=${versionParam}` : ""}`, { scroll: false });

  return (
    <div className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6">
      <Link href="/library" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="size-4" /> Library</Link>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl tracking-tight">{d.title}</h1>
          <p className="mt-1 flex flex-wrap gap-3 text-sm text-muted">
            <span>{d.collection}</span><span>{ver?.filename}</span>{ver?.page_count && <span>{ver.page_count} pages</span>}
            {typeof d.meta.effective_date === "string" && <span>effective {d.meta.effective_date}</span>}
            {d.source_uri && <a href={d.source_uri} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-teal">source <ExternalLink className="size-3" /></a>}
          </p>
        </div>
        <div role="group" aria-label="Versions" className="flex gap-1">
          {d.versions.map((v) => (
            <button key={v.id} onClick={() => router.replace(`${path}?version=${v.version}`)} aria-pressed={v.version === ver?.version} className={cn("rounded-full px-3 py-1 text-xs", v.version === ver?.version ? "bg-indigo text-paper" : "border border-line hover:bg-paper-2")}>
              v{v.version}{v.id === d.current?.id && " · current"}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div className="min-w-0">
          {isPdf ? (
            <PdfPage url={`/api/documents/${id}/file?version=${ver?.version}`} page={page ?? 1} highlight={selected?.text} />
          ) : (
            <Card className="p-8">
              <article className="mx-auto max-w-2xl space-y-4 font-serif text-[17px] leading-relaxed">
                {passages.data?.map((p) => (
                  <p key={p.id} id={`p-${p.id}`} className={cn("rounded-md transition-colors", p.id === selected?.id && "bg-teal-soft px-2 ring-1 ring-teal/40")}>
                    {p.section && (passages.data.find((x) => x.section === p.section)?.id === p.id) && <span className="mb-1 block font-sans text-xs uppercase tracking-widest text-muted">{p.section}</span>}
                    {p.text}
                  </p>
                ))}
              </article>
            </Card>
          )}
        </div>
        <aside aria-label="Passages">
          <h2 className="mb-2 flex items-center gap-2 font-serif text-lg"><FileText className="size-4 text-teal" /> Passages <span className="text-sm text-muted">({passages.data?.length ?? 0})</span></h2>
          <ol className="flex max-h-[75vh] flex-col gap-2 overflow-auto pr-1">
            {passages.data?.map((p) => (
              <li key={p.id} ref={p.id === selected?.id ? ref : undefined}>
                <button onClick={() => select(p.id)} className={cn("w-full rounded-xl border p-3 text-left text-sm transition-colors", p.id === selected?.id ? "border-teal bg-teal-soft" : "border-line bg-paper hover:bg-paper-2")}>
                  <span className="flex flex-wrap gap-1.5 text-[11px] text-muted">
                    <Chip>#{p.ordinal + 1}</Chip>{p.page && <Chip tone="indigo">p. {p.page}</Chip>}{p.section && <span className="truncate">{p.section}</span>}
                  </span>
                  <span className="mt-1.5 line-clamp-4 block">{p.text}</span>
                </button>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}

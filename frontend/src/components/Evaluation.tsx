"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, MinusCircle, XCircle } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Plot } from "./Plot";
import { Card, Empty, Skeleton } from "./ui";

type Retrieval = Record<"vector" | "keyword" | "hybrid", { recall_at_5: number; mrr_at_10: number; latency_ms_median: number; questions: number }>;
interface Summary { label: string; run_at: string; embedder: string; llm: string | null; documents: number; passages: number; index_ms: number; retrieval: Retrieval; answer_correct: number | null; citation_correct: number | null; groundedness: number | null; abstention_accuracy: number | null; conflict_detected: number | null; injection_resisted: number | null; latency_ms_median: number | null }
interface Row { id: string; question: string; status: string; latency_ms: number; supported: number; claims: number; answer: string[]; rejected: { text: string; reason: string }[]; answer_correct?: boolean; citation_correct?: number; abstention_correct: boolean; conflict_detected?: boolean; injection_resisted?: boolean }
interface Report { summary: Summary; questions: Row[] }

const ANSWER: [keyof Summary, string][] = [["answer_correct", "Answer correct"], ["citation_correct", "Citation correct"], ["groundedness", "Groundedness"], ["abstention_accuracy", "Abstention accuracy"], ["conflict_detected", "Conflict detected"], ["injection_resisted", "Injection resisted"]];
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`);

export function Evaluation() {
  const q = useQuery({ queryKey: ["evaluation"], queryFn: () => api.evaluation() as Promise<Report[]> });
  const [i, setI] = useState(0);
  if (q.isLoading) return <div className="p-8"><Skeleton className="h-80" /></div>;
  const reports = q.data ?? [];
  if (!reports.length) return <div className="mx-auto max-w-3xl p-8"><Empty icon={<FlaskConical className="size-5" />} title="No evaluation runs yet" action={<code className="rounded bg-paper-2 px-2 py-1 text-xs">make evaluate</code>}>Run the benchmark over the synthetic Halcyon corpus.</Empty></div>;
  const r = reports[Math.min(i, reports.length - 1)];
  const methods = ["vector", "keyword", "hybrid"] as const;
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <h1 className="font-serif text-3xl tracking-tight">Retrieval & answer evaluation</h1>
      <p className="mt-2 max-w-3xl text-sm text-muted">Measured runs of the benchmark over the synthetic Halcyon Devices corpus. Gold evidence is defined by document and required text. The <b>fixture-hashing</b> run uses a non-semantic hashing embedder and an extractive heuristic (no LLM) to test the pipeline; the <b>live</b> run uses nomic-embed-text and qwen3:4b-instruct locally.</p>
      <div role="tablist" aria-label="Runs" className="mt-6 flex flex-wrap gap-2">
        {reports.map((rep, k) => <button key={rep.summary.label} role="tab" aria-selected={k === i} onClick={() => setI(k)} className={cn("rounded-full px-4 py-1.5 text-sm", k === i ? "bg-indigo text-paper" : "border border-line bg-paper")}>{rep.summary.label}</button>)}
      </div>
      <p className="mt-2 text-xs text-muted">{new Date(r.summary.run_at).toLocaleString()} · {r.summary.embedder} · {r.summary.llm ?? "retrieval only"} · {r.summary.documents} documents · {r.summary.passages} passages · indexed in {(r.summary.index_ms / 1000).toFixed(1)}s</p>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-serif text-xl">Retrieval by method</h2>
          <Plot label="Recall@5 and MRR@10 per retrieval method" data={[{ type: "bar", name: "Recall@5", x: [...methods], y: methods.map((m) => r.summary.retrieval[m].recall_at_5) }, { type: "bar", name: "MRR@10", x: [...methods], y: methods.map((m) => r.summary.retrieval[m].mrr_at_10) }]} layout={{ barmode: "group", yaxis: { range: [0, 1.05], tickformat: ".0%" } }} />
        </Card>
        <Card className="p-5">
          <h2 className="font-serif text-xl">Answer quality</h2>
          <Plot label="Answer quality metrics" data={[{ type: "bar", orientation: "h", x: ANSWER.map(([k]) => (r.summary[k] as number | null) ?? 0), y: ANSWER.map(([, l]) => l), text: ANSWER.map(([k]) => pct(r.summary[k] as number | null)), textposition: "auto" }]} layout={{ xaxis: { range: [0, 1.05], tickformat: ".0%" }, margin: { l: 140, r: 16, t: 16, b: 40 } }} />
        </Card>
        <Card className="p-5 lg:col-span-2">
          <h2 className="font-serif text-xl">Latency per question</h2>
          <Plot label="Latency per question" height={260} data={[{ type: "bar", x: r.questions.map((x) => x.id), y: r.questions.map((x) => x.latency_ms / 1000), hovertemplate: "%{x}: %{y:.1f}s<extra></extra>" }]} layout={{ yaxis: { title: { text: "seconds" } } }} />
        </Card>
      </div>
      <Card className="mt-6 overflow-hidden">
        <h2 className="border-b border-line px-5 py-3 font-serif text-xl">Per-question results</h2>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-paper-2 text-left text-xs text-muted"><tr>{["Question", "Status", "Checks", "Answer (supported claims)", "Latency"].map((h) => <th key={h} scope="col" className="px-4 py-2 font-medium">{h}</th>)}</tr></thead>
            <tbody>
              {r.questions.map((x) => (
                <tr key={x.id} className="border-t border-line align-top">
                  <td className="px-4 py-2"><p className="font-medium">{x.id}</p><p className="max-w-xs text-xs text-muted">{x.question}</p></td>
                  <td className="px-4 py-2 text-xs">{x.status.replaceAll("_", " ")}<br /><span className="text-muted">{x.supported}/{x.claims} claims</span></td>
                  <td className="px-4 py-2 text-xs">
                    {x.answer_correct !== undefined && <Check ok={x.answer_correct} label="correct" />}
                    {x.citation_correct !== undefined && <Check ok={x.citation_correct >= 0.5} label={`citations ${pct(x.citation_correct)}`} />}
                    <Check ok={x.abstention_correct} label="abstention" />
                    {x.conflict_detected !== undefined && <Check ok={x.conflict_detected} label="conflict" />}
                    {x.injection_resisted !== undefined && <Check ok={x.injection_resisted} label="injection" />}
                  </td>
                  <td className="max-w-md px-4 py-2 text-xs">{x.answer.join(" ") || <span className="text-muted">(abstained)</span>}{x.rejected.length > 0 && <p className="mt-1 text-rose">rejected: {x.rejected[0].reason}</p>}</td>
                  <td className="px-4 py-2 text-xs">{(x.latency_ms / 1000).toFixed(1)}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Check({ ok, label }: { ok: boolean | undefined; label: string }) {
  const Icon = ok === undefined ? MinusCircle : ok ? CheckCircle2 : XCircle;
  return <span className="mr-2 inline-flex items-center gap-1"><Icon className={cn("size-3.5", ok ? "text-teal" : ok === false ? "text-rose" : "text-muted")} /> {label}</span>;
}

"use client";

import * as Collapsible from "@radix-ui/react-collapsible";
import * as Tabs from "@radix-ui/react-tabs";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowUp, Check, ChevronDown, CircleSlash, GitCompareArrows, History, Loader2, Quote, ShieldAlert, ShieldCheck, Square } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { api, streamResearch } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Answer, Claim, Conflict, Evidence, ResearchEvent, Session } from "@/lib/types";
import { EvidenceGraph } from "./EvidenceGraph";
import { Card, Chip, Empty, Skeleton } from "./ui";

const STAGES = ["understand", "retrieve", "assess", "reformulate", "rerank", "conflicts", "draft", "verify"];
const EXAMPLES = ["What is the current return window for refunds?", "How do I factory reset the Halcyon Hub H2?", "How often must service credentials be rotated?", "What warranty do partners get on Hub H2 orders?"];

interface Live { question: string; stages: Record<string, { status: string; ms?: number; round?: number }>; evidence: Evidence[]; quarantined: Session["quarantined"]; answer?: Answer; session?: Session; error?: string; calls: string[] }

export function Studio() {
  const qc = useQueryClient();
  const history = useQuery({ queryKey: ["sessions"], queryFn: api.sessions });
  const collections = useQuery({ queryKey: ["collections"], queryFn: api.collections });
  const [scope, setScope] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [live, setLive] = useState<Live | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [selectedPassage, setSelectedPassage] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const opened = useQuery({ queryKey: ["session", openId], queryFn: () => api.session(openId!), enabled: !!openId && openId !== live?.session?.id });
  const current: Session | undefined = live?.session ?? (openId ? opened.data : undefined);
  const running = !!live && !live.session && !live.error;

  const ask = useCallback(
    async (q: string, parent_id?: string | null) => {
      if (!q.trim()) return;
      abort.current?.abort();
      const ctrl = new AbortController();
      abort.current = ctrl;
      setQuestion("");
      setSelectedPassage(null);
      setOpenId(null);
      setLive({ question: q, stages: {}, evidence: [], quarantined: [], calls: [] });
      const on = (e: ResearchEvent) =>
        setLive((l) => {
          if (!l) return l;
          if (e.type === "stage") return { ...l, stages: { ...l.stages, [e.stage]: { status: e.status, ms: e.ms, round: e.round as number | undefined } } };
          if (e.type === "retrieval") return { ...l, calls: [...l.calls, ...e.calls.map((c) => `${c.query} → ${c.hits}`)] };
          if (e.type === "evidence") return { ...l, evidence: e.evidence, quarantined: e.quarantined };
          if (e.type === "answer") return { ...l, answer: e.answer };
          if (e.type === "done") return { ...l, session: e.session };
          if (e.type === "error") return { ...l, error: e.message };
          return l;
        });
      try {
        await streamResearch({ question: q, filters: scope.length ? { collections: scope } : {}, parent_id }, (e) => {
          on(e);
          if (e.type === "done") {
            setOpenId(e.session.id);
            qc.invalidateQueries({ queryKey: ["sessions"] });
          }
        }, ctrl.signal);
      } catch (err) {
        if (!ctrl.signal.aborted) setLive((l) => (l ? { ...l, error: err instanceof Error ? err.message : "failed" } : l));
      }
    },
    [qc, scope],
  );

  const evidence = current?.evidence ?? live?.evidence ?? [];
  const quarantined = current?.quarantined ?? live?.quarantined ?? [];
  const answer = current?.answer ?? live?.answer;
  const shownQuestion = current?.question ?? live?.question;

  return (
    <div className="mx-auto grid max-w-[1600px] gap-0 lg:grid-cols-[250px_minmax(0,1fr)_400px]">
      <aside className="hidden flex-col gap-5 border-r border-line p-4 lg:flex" aria-label="Scope and history">
        <section>
          <h2 className="mb-2 text-[11px] uppercase tracking-widest text-muted">Search scope</h2>
          <div className="flex flex-col gap-1">
            {(collections.data ?? []).map((c) => (
              <label key={c.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-paper-2">
                <input type="checkbox" checked={scope.includes(c.name)} onChange={(e) => setScope((s) => (e.target.checked ? [...s, c.name] : s.filter((x) => x !== c.name)))} />
                <span className="flex-1">{c.name}</span><span className="text-xs text-muted">{c.document_count}</span>
              </label>
            ))}
            <p className="px-2 text-[11px] text-muted">{scope.length ? `${scope.length} selected` : "All collections"}</p>
          </div>
        </section>
        <section className="min-h-0">
          <h2 className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-muted"><History className="size-3" /> History</h2>
          <ul className="flex max-h-[60vh] flex-col gap-0.5 overflow-auto">
            {(history.data ?? []).map((s) => (
              <li key={s.id}>
                <button onClick={() => (setLive(null), setOpenId(s.id), setSelectedPassage(null))} className={cn("w-full rounded-lg px-2 py-1.5 text-left text-sm", openId === s.id ? "bg-indigo-soft" : "hover:bg-paper-2")}>
                  <span className="line-clamp-2">{s.question}</span>
                  <span className="text-[11px] text-muted">{s.status.replaceAll("_", " ")}{s.parent_id && " · follow-up"}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </aside>

      <section className="flex min-h-[calc(100dvh-57px)] min-w-0 flex-col">
        <div className="flex-1 overflow-auto px-4 py-6 sm:px-8">
          {!shownQuestion && (
            <div className="mx-auto max-w-2xl">
              <Empty icon={<Quote className="size-5" />} title="Ask the library a question">Answers are drafted only from retrieved passages, and every claim is checked against the passage it cites.</Empty>
              <div className="mt-4 flex flex-wrap justify-center gap-2">{EXAMPLES.map((e) => <button key={e} onClick={() => ask(e)} className="rounded-full border border-line bg-paper px-3 py-1.5 text-xs text-muted hover:border-teal hover:text-ink">{e}</button>)}</div>
            </div>
          )}
          {shownQuestion && (
            <div className="mx-auto max-w-3xl">
              <p className="text-xs uppercase tracking-widest text-muted">Question</p>
              <h1 className="mt-1 font-serif text-3xl leading-tight tracking-tight">{shownQuestion}</h1>
              {live && !live.session && <Progress live={live} />}
              {live?.error && <p role="alert" className="mt-4 text-rose">{live.error}</p>}
              <Tabs.Root defaultValue="answer" className="mt-6">
                <Tabs.List aria-label="Result views" className="flex gap-1 border-b border-line">
                  {["answer", "graph"].map((t) => <Tabs.Trigger key={t} value={t} disabled={t === "graph" && !current} className="-mb-px border-b-2 border-transparent px-3 pb-2 text-sm capitalize text-muted data-[state=active]:border-indigo data-[state=active]:text-ink disabled:opacity-40">{t === "graph" ? "Evidence graph" : "Answer"}</Tabs.Trigger>)}
                </Tabs.List>
                <Tabs.Content value="answer" className="pt-5">
                  {answer ? <AnswerView answer={answer} onCite={setSelectedPassage} onFollowUp={(q) => ask(q, current?.id)} /> : running && <div className="flex flex-col gap-2"><Skeleton className="h-5 w-3/4" /><Skeleton className="h-5 w-1/2" /></div>}
                  {current && <p className="mt-6 text-[11px] text-muted">{current.model_name} · {current.embedder} · {((current.duration_ms ?? 0) / 1000).toFixed(1)} s · {current.llm_usage.calls} LLM calls</p>}
                </Tabs.Content>
                <Tabs.Content value="graph" className="pt-4">{current && <GraphTab id={current.id} onSelect={setSelectedPassage} />}</Tabs.Content>
              </Tabs.Root>
            </div>
          )}
        </div>
        <form onSubmit={(e) => (e.preventDefault(), ask(question))} className="border-t border-line bg-bg/80 px-4 py-3 backdrop-blur sm:px-8">
          <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-3xl border border-line bg-paper p-2 focus-within:border-teal">
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), ask(question))} rows={1} maxLength={2000} placeholder="Ask about policies, manuals, decisions…" aria-label="Research question" className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none" />
            {running ? (
              <button type="button" onClick={() => abort.current?.abort()} aria-label="Stop" className="grid size-10 place-items-center rounded-full bg-paper-2"><Square className="size-3.5" /></button>
            ) : (
              <button type="submit" disabled={!question.trim()} aria-label="Ask" className="grid size-10 place-items-center rounded-full bg-indigo text-paper disabled:opacity-40"><ArrowUp className="size-4" /></button>
            )}
          </div>
        </form>
      </section>

      <aside className="border-t border-line bg-paper lg:border-l lg:border-t-0" aria-label="Evidence inspector">
        <Inspector evidence={evidence} quarantined={quarantined} selected={selectedPassage} onSelect={setSelectedPassage} />
      </aside>
    </div>
  );
}

function Progress({ live }: { live: Live }) {
  return (
    <div className="mt-4">
      <ol className="flex flex-wrap gap-1.5" aria-label="Research progress">
        {STAGES.filter((s) => s !== "reformulate" || live.stages[s]).map((s) => {
          const st = live.stages[s];
          return (
            <li key={s} className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs", st?.status === "done" ? "border-teal/40 bg-teal-soft text-teal" : st ? "border-indigo/30 bg-indigo-soft text-indigo" : "border-line text-muted/60")}>
              {st?.status === "done" ? <Check className="size-3" /> : st ? <Loader2 className="size-3 animate-spin" /> : <span className="size-1.5 rounded-full bg-current" />}
              {s}{st?.round && s === "retrieve" ? ` ×${st.round}` : ""}{st?.ms !== undefined && <span className="opacity-70">{st.ms < 1000 ? `${Math.round(st.ms)}ms` : `${(st.ms / 1000).toFixed(1)}s`}</span>}
            </li>
          );
        })}
      </ol>
      {live.calls.length > 0 && <p className="mt-2 font-mono text-[11px] text-muted">search: {live.calls.slice(-3).join(" · ")}</p>}
    </div>
  );
}

function StatusBadge({ a }: { a: Answer }) {
  if (a.status === "verified") return <Chip tone="teal"><ShieldCheck className="size-3" /> all claims verified</Chip>;
  if (a.status === "partially_verified") return <Chip tone="sand"><ShieldAlert className="size-3" /> some claims rejected</Chip>;
  return <Chip tone="rose"><CircleSlash className="size-3" /> abstained</Chip>;
}

function AnswerView({ answer, onCite, onFollowUp }: { answer: Answer; onCite: (id: string) => void; onFollowUp: (q: string) => void }) {
  const ok = answer.claims.filter((c) => c.supported);
  const rejected = answer.claims.filter((c) => !c.supported);
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-5">
      <div className="flex items-center gap-2"><StatusBadge a={answer} /></div>
      {answer.abstain ? (
        <Card className="flex items-start gap-3 border-rose/30 bg-rose-soft p-5">
          <CircleSlash className="mt-0.5 size-5 shrink-0 text-rose" />
          <div><p className="font-serif text-lg">The sources do not establish an answer.</p><p className="mt-1 text-sm text-muted">{answer.reason}</p></div>
        </Card>
      ) : (
        <ol className="flex flex-col gap-3">
          {ok.map((c, i) => <ClaimItem key={i} c={c} onCite={onCite} />)}
        </ol>
      )}
      {answer.conflicts.length > 0 && <Conflicts conflicts={answer.conflicts} onCite={onCite} />}
      {rejected.length > 0 && (
        <Collapsible.Root className="rounded-2xl border border-line">
          <Collapsible.Trigger className="group flex w-full items-center gap-2 px-4 py-3 text-left text-sm text-muted">
            <AlertTriangle className="size-4 text-rose" /> {rejected.length} drafted claim{rejected.length > 1 ? "s" : ""} rejected by citation verification
            <ChevronDown className="ml-auto size-4 transition-transform group-data-[state=open]:rotate-180" />
          </Collapsible.Trigger>
          <Collapsible.Content className="border-t border-line px-4 py-3">
            <ul className="flex flex-col gap-2 text-sm">{rejected.map((c, i) => <li key={i}><p className="text-muted line-through decoration-rose/50">{c.text}</p><p className="text-xs text-rose">{c.support.reason}{c.invalid_citations.length > 0 && ` · invalid citation ${c.invalid_citations.join(", ")}`}</p></li>)}</ul>
          </Collapsible.Content>
        </Collapsible.Root>
      )}
      {answer.follow_ups.length > 0 && (
        <div>
          <p className="mb-2 text-xs uppercase tracking-widest text-muted">Follow-up research</p>
          <div className="flex flex-wrap gap-2">{answer.follow_ups.map((f) => <button key={f} onClick={() => onFollowUp(f)} className="rounded-full border border-line bg-paper px-3 py-1.5 text-xs hover:border-teal">{f}</button>)}</div>
        </div>
      )}
    </motion.div>
  );
}

function ClaimItem({ c, onCite }: { c: Claim; onCite: (id: string) => void }) {
  return (
    <li className="rounded-2xl border border-line bg-paper p-4">
      <p className="font-serif text-[17px] leading-relaxed">
        {c.text}{" "}
        {c.citations.map((x) => (
          <button key={x.ref} onClick={() => onCite(x.passage_id)} className="ml-0.5 rounded-md bg-teal-soft px-1.5 py-0.5 align-middle font-sans text-[11px] font-semibold text-teal hover:ring-1 hover:ring-teal" aria-label={`Show source ${x.ref}: ${x.document_title}`}>
            {x.ref}
          </button>
        ))}
      </p>
      <p className="mt-2 flex flex-wrap gap-2 text-[11px] text-muted">
        {c.citations.map((x) => <span key={x.ref}>{x.ref}: {x.document_title} v{x.version}{x.page ? ` · p.${x.page}` : ""}{x.section ? ` · ${x.section}` : ""}</span>)}
        <span>· support: lexical {c.support.lexical.toFixed(2)}{c.support.semantic > 0 && `, semantic ${c.support.semantic.toFixed(2)}`}</span>
      </p>
    </li>
  );
}

function Conflicts({ conflicts, onCite }: { conflicts: Conflict[]; onCite: (id: string) => void }) {
  return (
    <Card className="border-sand/60 bg-sand-soft p-5">
      <h3 className="flex items-center gap-2 font-serif text-lg"><GitCompareArrows className="size-5" /> Conflicting sources</h3>
      <ul className="mt-3 flex flex-col gap-3 text-sm">
        {conflicts.map((c, i) => (
          <li key={i}>
            <p>{c.explanation || c.detail}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {[{ ref: c.a, id: c.a_passage }, { ref: c.b, id: c.b_passage }].map((x) => (
                <button key={x.ref} onClick={() => onCite(x.id)} className={cn("rounded-full px-2.5 py-1 text-xs font-semibold", x.ref === c.newer ? "bg-teal text-paper" : "bg-paper")}>{x.ref}{x.ref === c.newer && " · newer"}</button>
              ))}
              <span className="text-xs text-muted">{c.detail}{Array.isArray(c.signals.effective_dates) && ` · effective ${(c.signals.effective_dates as (string | null)[]).map((d) => d ?? "?").join(" vs ")}`}</span>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function GraphTab({ id, onSelect }: { id: string; onSelect: (pid: string) => void }) {
  const g = useQuery({ queryKey: ["graph", id], queryFn: () => api.graph(id) });
  if (!g.data) return <Skeleton className="h-[520px]" />;
  return <Card className="h-[560px] overflow-hidden"><EvidenceGraph data={g.data} onSelectPassage={onSelect} /></Card>;
}

function Inspector({ evidence, quarantined, selected, onSelect }: { evidence: Evidence[]; quarantined: Session["quarantined"]; selected: string | null; onSelect: (id: string | null) => void }) {
  const detail = useQuery({ queryKey: ["passage", selected], queryFn: () => api.passage(selected!), enabled: !!selected });
  const ev = evidence.find((e) => e.passage_id === selected);
  return (
    <div className="flex h-full flex-col">
      <AnimatePresence mode="wait">
        {selected && detail.data ? (
          <motion.div key={selected} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="border-b border-line p-4">
            <div className="flex items-start justify-between gap-2">
              <div><p className="text-xs text-muted">{ev?.ref ?? "passage"} · source</p><h3 className="font-serif text-lg leading-snug">{detail.data.document.title}</h3></div>
              <button onClick={() => onSelect(null)} className="text-xs text-muted hover:text-ink">close</button>
            </div>
            <p className="mt-1 flex flex-wrap gap-1.5 text-[11px]"><Chip tone="indigo">v{detail.data.document.version}</Chip>{detail.data.passage.page && <Chip>p. {detail.data.passage.page}</Chip>}{detail.data.passage.section && <Chip>{detail.data.passage.section}</Chip>}{typeof detail.data.document.meta.effective_date === "string" && <Chip tone="sand">effective {detail.data.document.meta.effective_date}</Chip>}</p>
            <div className="mt-3 max-h-64 overflow-auto rounded-xl bg-bg p-3 text-sm leading-relaxed">
              {detail.data.context.map((p) => <p key={p.id} className={cn("mb-2", p.id === selected ? "rounded bg-teal-soft px-1" : "text-muted")}>{p.text}</p>)}
            </div>
            <Link href={`/documents/${detail.data.document.id}?passage=${selected}&version=${detail.data.document.version}`} className="mt-3 inline-block text-sm font-medium text-teal">Open in document viewer →</Link>
          </motion.div>
        ) : null}
      </AnimatePresence>
      <div className="flex-1 overflow-auto p-4">
        <h2 className="mb-2 text-[11px] uppercase tracking-widest text-muted">Evidence ({evidence.length})</h2>
        {evidence.length === 0 && <p className="text-sm text-muted">Retrieved passages appear here as the agent searches.</p>}
        <ol className="flex flex-col gap-2">
          {evidence.map((e) => (
            <li key={e.passage_id}>
              <button onClick={() => onSelect(e.passage_id)} className={cn("w-full rounded-xl border p-3 text-left text-sm", selected === e.passage_id ? "border-teal bg-teal-soft" : "border-line hover:bg-paper-2")}>
                <span className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                  <span className="font-semibold text-teal">{e.ref}</span><span className="truncate">{e.document_title}</span>{e.page && <span>p.{e.page}</span>}
                  {Object.entries(e.ranks).map(([m, r]) => <Chip key={m}>{m} #{r}</Chip>)}{e.sanitized && <Chip tone="rose">sanitised</Chip>}
                </span>
                <span className="mt-1 line-clamp-3 block">{e.text}</span>
              </button>
            </li>
          ))}
        </ol>
        {quarantined.length > 0 && (
          <div className="mt-5">
            <h2 className="mb-2 flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-rose"><ShieldAlert className="size-3" /> Quarantined text ({quarantined.length})</h2>
            {quarantined.map((q) => (
              <div key={q.passage_id} className="mb-2 rounded-xl border border-rose/30 bg-rose-soft p-3 text-xs">
                <p className="font-medium">{q.document_title}</p>
                <p className="mt-1 text-muted">{q.reason}</p>
                {q.removed_sentences?.map((s) => <p key={s} className="mt-1 font-mono line-through">{s}</p>)}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

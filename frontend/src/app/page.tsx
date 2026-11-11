import { ArrowRight, GitCompareArrows, Network, Quote, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { Wordmark } from "@/components/Logo";

const FEATURES = [
  { icon: Quote, title: "Every claim cited", body: "Answers are lists of claims, each linked to the exact passage, page and document version that states it." },
  { icon: ShieldCheck, title: "Verified, or withheld", body: "Claims are checked against their citations for numbers, negation and subject. Unsupported claims are shown as rejected, never as fact." },
  { icon: GitCompareArrows, title: "Conflicts surfaced", body: "When two sources disagree, both are shown with their effective dates instead of one being silently chosen." },
  { icon: Network, title: "Evidence you can walk", body: "An evidence graph connects the question, claims, passages and documents through recorded relationships." },
];

export default function Landing() {
  return (
    <div className="paper-texture min-h-dvh">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Wordmark />
        <Link href="/studio" className="inline-flex items-center gap-2 rounded-full bg-indigo px-5 py-2.5 text-sm font-medium text-paper">Open the studio <ArrowRight className="size-4" /></Link>
      </header>
      <section className="mx-auto max-w-4xl px-6 pb-16 pt-14 text-center">
        <p className="text-xs uppercase tracking-[0.25em] text-teal">Agentic retrieval · hybrid search · verified citations</p>
        <h1 className="mt-5 font-serif text-5xl leading-[1.05] tracking-tight sm:text-7xl">Explore knowledge.<br /><em className="text-indigo">Trace every answer.</em></h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted">SourceAtlas reads your documents, searches them with pgvector and full-text retrieval, checks whether the evidence is sufficient, and answers only with claims it can trace to a source passage.</p>
        <div className="mt-9 flex justify-center gap-3">
          <Link href="/studio" className="rounded-full bg-indigo px-6 py-3 font-medium text-paper">Ask the library</Link>
          <Link href="/library" className="rounded-full border border-line bg-paper px-6 py-3 font-medium">Browse sources</Link>
        </div>
      </section>
      <section className="mx-auto grid max-w-6xl gap-4 px-6 pb-20 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <article key={title} className="rounded-2xl border border-line bg-paper p-6">
            <Icon className="size-5 text-teal" aria-hidden />
            <h2 className="mt-4 font-serif text-xl">{title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">{body}</p>
          </article>
        ))}
      </section>
      <footer className="pb-10 text-center text-xs text-muted">The demo library describes a fictional company and is entirely synthetic.</footer>
    </div>
  );
}

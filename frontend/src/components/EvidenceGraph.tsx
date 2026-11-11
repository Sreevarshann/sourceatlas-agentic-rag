"use client";

import { Background, Controls, type Edge, MarkerType, type Node, ReactFlow } from "@xyflow/react";
import { useMemo, useState } from "react";
import type { GraphData } from "@/lib/types";
import { cn } from "@/lib/cn";

const COL = { question: 0, claim: 320, passage: 700, document: 1080 } as const;
const COLORS: Record<string, string> = { supports: "var(--teal)", unsupported: "var(--rose)", conflicts: "var(--sand)", retrieved: "var(--line)", answers: "var(--indigo)", in_document: "var(--line)" };

/** Evidence graph built only from recorded relationships (retrieval, citations, conflicts). */
export function EvidenceGraph({ data, onSelectPassage }: { data: GraphData; onSelectPassage?: (passageId: string) => void }) {
  const [focus, setFocus] = useState<string | null>(null);
  const [showDocs, setShowDocs] = useState(true);
  const [showRetrieved, setShowRetrieved] = useState(false);

  const { nodes, edges } = useMemo(() => {
    const visible = data.nodes.filter((n) => showDocs || n.type !== "document");
    const counters: Record<string, number> = {};
    const linked = new Set<string>();
    if (focus) {
      linked.add(focus);
      for (const e of data.edges) {
        if (e.source === focus) linked.add(e.target);
        if (e.target === focus) linked.add(e.source);
      }
    }
    const nodes: Node[] = visible.map((n) => {
      const i = (counters[n.type] = (counters[n.type] ?? -1) + 1);
      const dim = focus !== null && !linked.has(n.id);
      // "!" so these win over React Flow's default (white) node styles in both themes
      const tone = n.type === "question" ? "!border-indigo !bg-indigo !text-paper" : n.type === "claim" ? (n.supported ? "!border-teal !bg-teal-soft !text-ink" : "!border-rose !bg-rose-soft !text-ink") : n.type === "document" ? "!border-sand !bg-sand-soft !text-ink" : "!border-line !bg-paper !text-ink";
      return {
        id: n.id,
        position: { x: COL[n.type], y: n.type === "question" ? 160 : 20 + i * (n.type === "passage" ? 92 : 110) },
        data: { label: <div className="text-left"><p className="text-[10px] uppercase tracking-wider opacity-70">{n.type}{n.type === "passage" && typeof n.page === "number" ? ` · p.${n.page}` : ""}</p><p className="line-clamp-3 text-xs">{n.label}</p></div> },
        className: cn("!w-[260px] !rounded-xl !border !p-2 !shadow-sm transition-opacity", tone, dim && "opacity-25"),
        sourcePosition: "right" as never,
        targetPosition: "left" as never,
      };
    });
    const ids = new Set(nodes.map((n) => n.id));
    const edges: Edge[] = data.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target) && (showRetrieved || e.kind !== "retrieved"))
      .map((e) => ({ id: e.id, source: e.source, target: e.target, animated: e.kind === "conflicts", label: e.kind === "conflicts" ? "conflicts" : e.kind === "unsupported" ? "not supported" : undefined, style: { stroke: COLORS[e.kind], strokeWidth: e.kind === "supports" ? 2.2 : 1.2, strokeDasharray: e.kind === "unsupported" ? "5 4" : undefined, opacity: focus && !(linked.has(e.source) && linked.has(e.target)) ? 0.15 : 1 }, markerEnd: { type: MarkerType.ArrowClosed, color: COLORS[e.kind] } }));
    return { nodes, edges };
  }, [data, focus, showDocs, showRetrieved]);

  return (
    <div className="flex h-full min-h-[520px] flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-3 py-2 text-xs">
        <label className="flex items-center gap-1.5"><input type="checkbox" checked={showDocs} onChange={(e) => setShowDocs(e.target.checked)} /> documents</label>
        <label className="flex items-center gap-1.5"><input type="checkbox" checked={showRetrieved} onChange={(e) => setShowRetrieved(e.target.checked)} /> retrieval edges</label>
        <span className="flex items-center gap-1"><i className="h-0.5 w-4 bg-teal" /> supports</span>
        <span className="flex items-center gap-1"><i className="h-0.5 w-4 border-t border-dashed border-rose" /> not supported</span>
        <span className="flex items-center gap-1"><i className="h-0.5 w-4 bg-sand" /> conflicts</span>
        {focus && <button onClick={() => setFocus(null)} className="ml-auto rounded-full border border-line px-2 py-0.5">clear focus</button>}
      </div>
      <div className="flex-1" aria-label="Evidence graph" role="figure">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          minZoom={0.2}
          nodesConnectable={false}
          onNodeClick={(_, n) => {
            setFocus((f) => (f === n.id ? null : n.id));
            if (n.id.startsWith("p:")) onSelectPassage?.(n.id.slice(2));
          }}
        >
          <Background gap={22} color="var(--line)" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}

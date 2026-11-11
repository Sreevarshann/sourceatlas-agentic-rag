"use client";

import { useEffect, useRef, useState } from "react";
import { Skeleton } from "./ui";

type PdfModule = typeof import("pdfjs-dist");
let pdfjs: Promise<PdfModule> | null = null;
function load(): Promise<PdfModule> {
  pdfjs ??= import("pdfjs-dist").then((m) => {
    m.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
    return m;
  });
  return pdfjs;
}

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();

/** Renders one PDF page and highlights the text items that belong to `highlight`. */
export function PdfPage({ url, page, highlight, width = 720 }: { url: string; page: number; highlight?: string; width?: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [boxes, setBoxes] = useState<{ left: number; top: number; width: number; height: number }[]>([]);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const lib = await load();
        const doc = await lib.getDocument({ url }).promise;
        const p = await doc.getPage(Math.min(page, doc.numPages));
        const base = p.getViewport({ scale: 1 });
        const viewport = p.getViewport({ scale: width / base.width });
        const c = canvas.current;
        if (!c || cancelled) return;
        const ratio = window.devicePixelRatio || 1;
        c.width = viewport.width * ratio;
        c.height = viewport.height * ratio;
        c.style.width = `${viewport.width}px`;
        c.style.height = `${viewport.height}px`;
        await p.render({ canvas: c, viewport: p.getViewport({ scale: (width / base.width) * ratio }) }).promise;
        setSize({ w: viewport.width, h: viewport.height });
        if (highlight) {
          const target = norm(highlight);
          const content = await p.getTextContent();
          const out: typeof boxes = [];
          for (const item of content.items) {
            if (!("str" in item) || item.str.trim().length < 2) continue;
            if (!target.includes(norm(item.str))) continue;
            const [, , , fh, x, y] = item.transform as number[];
            const [vx, vy] = viewport.convertToViewportPoint(x, y);
            const h = Math.abs(fh) * viewport.scale;
            out.push({ left: vx, top: vy - h, width: item.width * viewport.scale, height: h * 1.15 });
          }
          if (!cancelled) setBoxes(out);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not render PDF");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [url, page, highlight, width]);

  if (error) return <p role="alert" className="text-sm text-rose">{error}</p>;
  return (
    <div className="relative mx-auto w-fit overflow-hidden rounded-xl border border-line bg-white shadow-sm" aria-label={`PDF page ${page}`}>
      {!size && <Skeleton className="absolute inset-0 h-full" />}
      <canvas ref={canvas} role="img" aria-label={`Rendered page ${page}`} />
      {boxes.map((b, i) => <span key={i} aria-hidden className="pointer-events-none absolute rounded-sm bg-[color-mix(in_oklab,var(--teal)_30%,transparent)] ring-1 ring-teal/50" style={b} />)}
    </div>
  );
}

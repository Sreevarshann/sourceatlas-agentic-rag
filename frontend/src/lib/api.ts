import type { Collection, Doc, GraphData, Passage, ResearchEvent, Session } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { ...init, headers: init?.body instanceof FormData ? init?.headers : { "Content-Type": "application/json", ...init?.headers } });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const d = (await res.json()).detail;
      msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: { msg?: string }) => x.msg).join("; ") : msg;
    } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  health: () => req<{ status: string; version: string; embedding_model: string; embedding_provider: string; llm_provider: string; pgvector: string | null }>("/health"),
  collections: () => req<Collection[]>("/collections"),
  documents: (p: { collection?: string; q?: string; tag?: string } = {}) => req<Doc[]>(`/documents?${new URLSearchParams(Object.entries(p).filter(([, v]) => v) as [string, string][])}`),
  document: (id: string) => req<Doc>(`/documents/${id}`),
  passages: (id: string, version?: number) => req<Passage[]>(`/documents/${id}/passages${version ? `?version=${version}` : ""}`),
  passage: (id: string) => req<{ passage: Passage; context: Passage[]; document: { id: string; title: string; version: number; filename: string; mime: string; meta: Record<string, unknown>; source_uri: string | null } }>(`/passages/${id}?context=2`),
  upload: (fd: FormData) => req<Doc>("/documents", { method: "POST", body: fd }),
  newVersion: (id: string, fd: FormData) => req<Doc>(`/documents/${id}/versions`, { method: "POST", body: fd }),
  ingestUrl: (url: string, collection: string) => req<Doc>("/documents/web", { method: "POST", body: JSON.stringify({ url, collection }) }),
  reindex: (id: string) => req<Doc>(`/documents/${id}/reindex`, { method: "POST" }),
  remove: (id: string) => req<void>(`/documents/${id}`, { method: "DELETE" }),
  sessions: () => req<Session[]>("/research"),
  session: (id: string) => req<Session>(`/research/${id}`),
  graph: (id: string) => req<GraphData>(`/research/${id}/graph`),
  evaluation: () => fetch("/api/evaluation").then((r) => r.json()),
};

export async function streamResearch(body: { question: string; filters?: Record<string, unknown>; parent_id?: string | null }, onEvent: (e: ResearchEvent) => void, signal?: AbortSignal) {
  const res = await fetch("/api/research/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  if (!res.ok || !res.body) throw new Error("Could not start research");
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const data = chunk.split("\n").filter((l) => l.startsWith("data: ")).map((l) => l.slice(6)).join("\n");
      if (data) onEvent(JSON.parse(data) as ResearchEvent);
    }
  }
}

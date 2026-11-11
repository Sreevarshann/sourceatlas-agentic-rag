export interface Version { id: string; version: number; filename: string; mime: string; sha256: string; size_bytes: number; status: "pending" | "processing" | "ready" | "failed"; error: string | null; page_count: number | null; passage_count: number; embedding_model: string | null; created_at: string; processed_at: string | null }
export interface Doc { id: string; collection_id: string; collection: string; title: string; source_type: "upload" | "web"; source_uri: string | null; tags: string[]; meta: Record<string, unknown>; created_at: string; status: Version["status"]; current: Version | null; versions: Version[] }
export interface Collection { id: string; name: string; description: string | null; document_count: number }
export interface Passage { id: string; document_id: string; version_id: string; ordinal: number; page: number | null; section: string | null; text: string; char_start: number; char_end: number; token_count: number }
export interface Evidence { passage_id: string; document_id: string; version_id: string; document_title: string; collection: string; version: number; page: number | null; section: string | null; text: string; ordinal: number; score: number; ranks: Record<string, number>; scores: Record<string, number>; meta: Record<string, unknown>; source_uri: string | null; ref: string; coverage?: number; rerank_score?: number; sanitized?: boolean; query?: string }
export interface Citation { ref: string; passage_id: string; document_id: string; document_title: string; version: number; page: number | null; section: string | null; excerpt: string; source_uri: string | null }
export interface Claim { text: string; citations: Citation[]; invalid_citations: string[]; supported: boolean; support: { supported: boolean; lexical: number; semantic: number; numbers_ok: boolean; reason: string } }
export interface Conflict { a: string; b: string; a_passage: string; b_passage: string; kind: string; detail: string; explanation: string; newer: string | null; signals: Record<string, unknown> }
export interface Answer { status: "verified" | "partially_verified" | "abstained"; abstain: boolean; reason: string | null; claims: Claim[]; conflicts: Conflict[]; follow_ups: string[]; intent: string }
export interface TraceEntry { node: string; ms: number; [k: string]: unknown }
export interface Session { id: string; question: string; parent_id: string | null; status: string; answer: Answer | null; evidence: Evidence[]; quarantined: (Evidence & { removed_sentences?: string[]; reason: string })[]; trace: TraceEntry[]; model_name: string | null; embedder: string | null; llm_usage: Record<string, number>; duration_ms: number | null; created_at: string }
export interface GraphData { nodes: { id: string; type: "question" | "claim" | "passage" | "document"; label: string; [k: string]: unknown }[]; edges: { id: string; source: string; target: string; kind: "retrieved" | "in_document" | "answers" | "supports" | "unsupported" | "conflicts"; [k: string]: unknown }[] }
export type ResearchEvent =
  | { type: "session"; id: string }
  | { type: "stage"; stage: string; status: "start" | "done"; ms?: number; [k: string]: unknown }
  | { type: "retrieval"; round: number; calls: { query: string; hits: number }[]; quarantined: number }
  | { type: "evidence"; evidence: Evidence[]; quarantined: Session["quarantined"] }
  | { type: "conflicts"; conflicts: Conflict[] }
  | { type: "answer"; answer: Answer }
  | { type: "done"; session: Session }
  | { type: "error"; message: string };

// src/api/types.ts
export type MemoryType = "semantic" | "fact" | "session" | "node" | "edge";

export interface Scope {
  tenant?: string | null;
  user?: string | null;
  agent?: string | null;
  session?: string | null;
}

export interface Relation {
  predicate: string;
  target_id: string;
}

export interface MemoryRecord {
  id: string;
  type: MemoryType;
  content: string;
  data: Record<string, unknown>;
  relations: Relation[];
  scope: Scope;
  metadata: Record<string, unknown>;
  ttl: number | null;
  created_at: string;
  updated_at: string;
  schema_version: string;
}

export interface SearchResult {
  results: MemoryRecord[];
  text: string;
}

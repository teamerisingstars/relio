// src/api/client.ts
import type { MemoryRecord, SearchResult } from "./types";

const BASE = "/api";

export async function addMemory(
  content: string,
  opts: { user?: string } = {},
): Promise<MemoryRecord> {
  const res = await fetch(`${BASE}/memory`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, user: opts.user }),
  });
  if (!res.ok) throw new Error(`addMemory failed: ${res.status}`);
  return res.json();
}

export async function searchMemory(
  q: string,
  opts: { user?: string; limit?: number } = {},
): Promise<SearchResult> {
  const params = new URLSearchParams({ q });
  if (opts.user) params.set("user", opts.user);
  if (opts.limit) params.set("limit", String(opts.limit));
  const res = await fetch(`${BASE}/memory/search?${params.toString()}`);
  if (!res.ok) throw new Error(`searchMemory failed: ${res.status}`);
  return res.json();
}

export async function deleteMemory(id: string): Promise<{ deleted: boolean }> {
  const res = await fetch(`${BASE}/memory/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`deleteMemory failed: ${res.status}`);
  return res.json();
}

export async function* chatStream(
  message: string,
  opts: { user?: string } = {},
): AsyncGenerator<string> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, user: opts.user }),
  });
  if (!res.ok || !res.body) throw new Error(`chat failed: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (!frame.startsWith("data:")) continue;
      const payload = JSON.parse(frame.slice(frame.indexOf(":") + 1).trim());
      if (payload.error) throw new Error(payload.error);
      if (payload.done) return;
      if (typeof payload.delta === "string") yield payload.delta;
    }
  }
}

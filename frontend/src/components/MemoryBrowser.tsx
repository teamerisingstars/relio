// src/components/MemoryBrowser.tsx
import { useState } from "react";
import type { FormEvent } from "react";
import { addMemory, searchMemory, deleteMemory } from "../api/client";
import type { MemoryRecord } from "../api/types";

export function MemoryBrowser({ user }: { user: string }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<MemoryRecord[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  async function doSearch(e?: FormEvent) {
    e?.preventDefault();
    setError("");
    try {
      const res = await searchMemory(q, { user });
      setResults(res.results);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function doAdd(e: FormEvent) {
    e.preventDefault();
    const content = draft.trim();
    if (!content) return;
    setDraft("");
    try {
      await addMemory(content, { user });
      await doSearch();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function doDelete(id: string) {
    try {
      await deleteMemory(id);
      setResults((r) => r.filter((x) => x.id !== id));
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <aside className="browser">
      <h2 className="browser-title">Memory</h2>
      <form className="search" onSubmit={doSearch}>
        <input
          aria-label="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search memories…"
        />
        <button type="submit">Search</button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <ul className="results" aria-label="results">
        {results.map((r) => (
          <li key={r.id} className="result">
            <span className="result-content">{r.content}</span>
            <span className="chip">{r.type}</span>
            <button aria-label={`delete ${r.id}`} onClick={() => void doDelete(r.id)}>
              ×
            </button>
          </li>
        ))}
      </ul>
      <form className="add" onSubmit={doAdd}>
        <input
          aria-label="new memory"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add a memory…"
        />
        <button type="submit">Add</button>
      </form>
    </aside>
  );
}

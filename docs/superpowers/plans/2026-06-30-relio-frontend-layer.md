# Relio Frontend Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. When building the UI components/styles, also use the **frontend-design** skill for polish.

**Goal:** Build the Relio frontend — a Vite + React + TypeScript SPA with a streaming chat view and a memory browser, talking to the backend over `/api`.

**Architecture:** A hand-written typed API client (memory CRUD + SSE chat stream) under a two-pane React UI. Vitest + React Testing Library component tests with the client/fetch mocked are the gate — no live backend needed.

**Tech Stack:** Node.js + npm, Vite 5, React 18, TypeScript 5, Vitest 2, @testing-library/react, jsdom.

---

## File Structure

```
relio/frontend/
  package.json
  tsconfig.json
  vite.config.ts
  index.html
  tests/
    setup.ts
    smoke.test.tsx
    client.test.ts
    ChatView.test.tsx
    MemoryBrowser.test.tsx
  src/
    main.tsx
    App.tsx
    styles.css
    api/
      types.ts
      client.ts
    components/
      ChatView.tsx
      MemoryBrowser.tsx
```

All commands run from `relio/frontend`. Node.js + npm must be available.

---

### Task 0: Scaffold + toolchain smoke test

**Files:**
- Create: `relio/frontend/package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `tests/setup.ts`, `src/main.tsx`, `src/App.tsx`, `src/styles.css`, `tests/smoke.test.tsx`

- [ ] **Step 1: Create the config + entry files**

`relio/frontend/package.json`:
```json
{
  "name": "relio-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0"
  }
}
```

`relio/frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2021",
    "lib": ["ES2021", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"],
    "noEmit": true
  },
  "include": ["src", "tests"]
}
```

`relio/frontend/vite.config.ts`:
```ts
/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./tests/setup.ts",
  },
});
```

`relio/frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Relio</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
      rel="stylesheet"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`relio/frontend/tests/setup.ts`:
```ts
import "@testing-library/jest-dom";
```

`relio/frontend/src/styles.css`:
```css
:root {
  --canvas: #faf7f2;
  --surface: #ffffff;
  --ink: #1b1a17;
  --muted: #6b655c;
  --accent: #2f6f62;
  --accent-soft: #e7efec;
  --line: #e9e3da;
  --radius: 14px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--canvas);
  color: var(--ink);
  font-family: "IBM Plex Sans", ui-sans-serif, sans-serif;
}
.brand {
  font-family: "Fraunces", Georgia, serif;
  font-weight: 600;
  font-size: 1.4rem;
  letter-spacing: 0.2px;
}
```

`relio/frontend/src/App.tsx`:
```tsx
export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Relio</span>
      </header>
    </div>
  );
}
```

`relio/frontend/src/main.tsx`:
```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

`relio/frontend/tests/smoke.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import App from "../src/App";

test("App renders the brand", () => {
  render(<App />);
  expect(screen.getByText("Relio")).toBeInTheDocument();
});
```

- [ ] **Step 2: Install dependencies**

Run: `cd relio/frontend && npm install`
Expected: installs without errors (creates `node_modules` + `package-lock.json`).

- [ ] **Step 3: Run the smoke test**

Run: `cd relio/frontend && npm test`
Expected: PASS — `smoke.test.tsx` green (1 passed). Confirms Vite + React + Vitest + jsdom + Testing Library all work.

- [ ] **Step 4: Add a .gitignore entry for node_modules**

Append to the repo-root `.gitignore` (`C:\Users\teame\OneDrive\Desktop\memmory test\.gitignore`):
```
# Frontend
node_modules/
relio/frontend/dist/
```

- [ ] **Step 5: Commit**

```bash
git add relio/frontend/package.json relio/frontend/package-lock.json relio/frontend/tsconfig.json relio/frontend/vite.config.ts relio/frontend/index.html relio/frontend/tests/setup.ts relio/frontend/tests/smoke.test.tsx relio/frontend/src .gitignore
git commit -m "chore: scaffold Relio frontend (Vite + React + Vitest)"
```

---

### Task 1: API types

**Files:**
- Create: `relio/frontend/src/api/types.ts`

(Types are compile-time only; they're exercised by the client tests in Task 2. This task just defines them.)

- [ ] **Step 1: Write the types**

```ts
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
```

- [ ] **Step 2: Type-check**

Run: `cd relio/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add relio/frontend/src/api/types.ts
git commit -m "feat: frontend API types"
```

---

### Task 2: API client — memory CRUD

**Files:**
- Create: `relio/frontend/src/api/client.ts`
- Test: `relio/frontend/tests/client.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// tests/client.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { addMemory, searchMemory, deleteMemory } from "../src/api/client";

afterEach(() => vi.restoreAllMocks());

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("memory client", () => {
  it("addMemory posts content + user and returns the record", async () => {
    const rec = { id: "mem_1", content: "hi", type: "semantic" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(rec));
    const out = await addMemory("hi", { user: "you" });
    expect(out).toEqual(rec);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/memory");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ content: "hi", user: "you" });
  });

  it("searchMemory builds the query string and returns results", async () => {
    const body = { results: [{ id: "mem_1", content: "hi", type: "semantic" }], text: "- hi" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(body));
    const out = await searchMemory("hi", { user: "you", limit: 3 });
    expect(out.results).toHaveLength(1);
    expect(out.text).toBe("- hi");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/memory/search?q=hi&user=you&limit=3");
  });

  it("deleteMemory DELETEs by id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ deleted: true }));
    const out = await deleteMemory("mem_1");
    expect(out).toEqual({ deleted: true });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/memory/mem_1");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("DELETE");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio/frontend && npx vitest run tests/client.test.ts`
Expected: FAIL — cannot resolve `../src/api/client`.

- [ ] **Step 3: Write the implementation**

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio/frontend && npx vitest run tests/client.test.ts`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add relio/frontend/src/api/client.ts relio/frontend/tests/client.test.ts
git commit -m "feat: memory CRUD API client"
```

---

### Task 3: API client — SSE chat stream

**Files:**
- Modify: `relio/frontend/src/api/client.ts` (add `chatStream`)
- Test: `relio/frontend/tests/client.test.ts` (append)

- [ ] **Step 1: Write the failing test**

```ts
// tests/client.test.ts  (append)
import { chatStream } from "../src/api/client";

function sseResponse(frames: string[]) {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(enc.encode(f));
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

describe("chatStream", () => {
  it("yields deltas and stops at done", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      sseResponse([
        'data: {"delta": "Hel"}\n\n',
        'data: {"delta": "lo"}\n\n',
        'data: {"done": true}\n\n',
      ]),
    );
    const out: string[] = [];
    for await (const d of chatStream("hi", { user: "you" })) out.push(d);
    expect(out.join("")).toBe("Hello");
  });

  it("throws on an error frame", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      sseResponse(['data: {"error": "boom"}\n\n']),
    );
    await expect(async () => {
      for await (const _ of chatStream("hi")) void _;
    }).rejects.toThrow("boom");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio/frontend && npx vitest run tests/client.test.ts`
Expected: FAIL — `chatStream` is not exported.

- [ ] **Step 3: Add the implementation**

Append to `src/api/client.ts`:
```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio/frontend && npx vitest run tests/client.test.ts`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add relio/frontend/src/api/client.ts relio/frontend/tests/client.test.ts
git commit -m "feat: SSE chatStream client"
```

---

### Task 4: ChatView component

**Files:**
- Create: `relio/frontend/src/components/ChatView.tsx`
- Test: `relio/frontend/tests/ChatView.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// tests/ChatView.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ChatView } from "../src/components/ChatView";

vi.mock("../src/api/client", () => ({
  chatStream: vi.fn(async function* () {
    yield "Hi ";
    yield "there";
  }),
}));

test("sends a message and renders the streamed reply", async () => {
  const user = userEvent.setup();
  render(<ChatView user="you" />);
  await user.type(screen.getByLabelText("message"), "hello");
  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("hello")).toBeInTheDocument();        // user bubble
  expect(await screen.findByText("Hi there")).toBeInTheDocument();     // streamed assistant bubble
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio/frontend && npx vitest run tests/ChatView.test.tsx`
Expected: FAIL — cannot resolve `../src/components/ChatView`.

- [ ] **Step 3: Write the implementation**

```tsx
// src/components/ChatView.tsx
import { useState } from "react";
import { chatStream } from "../api/client";

interface Msg {
  role: "user" | "assistant";
  text: string;
}

export function ChatView({ user }: { user: string }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", text: "" }]);
    try {
      for await (const delta of chatStream(text, { user })) {
        setMessages((m) => {
          const copy = m.slice();
          const last = copy[copy.length - 1];
          copy[copy.length - 1] = { role: "assistant", text: last.text + delta };
          return copy;
        });
      }
    } catch (err) {
      setMessages((m) => {
        const copy = m.slice();
        copy[copy.length - 1] = { role: "assistant", text: `⚠️ ${(err as Error).message}` };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="chat">
      <ul className="messages" aria-label="messages">
        {messages.map((m, i) => (
          <li key={i} className={`bubble ${m.role}`}>
            {m.text}
          </li>
        ))}
      </ul>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          aria-label="message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Relio…"
          disabled={busy}
        />
        <button type="submit" disabled={busy}>
          Send
        </button>
      </form>
    </section>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio/frontend && npx vitest run tests/ChatView.test.tsx`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add relio/frontend/src/components/ChatView.tsx relio/frontend/tests/ChatView.test.tsx
git commit -m "feat: streaming ChatView component"
```

---

### Task 5: MemoryBrowser component

**Files:**
- Create: `relio/frontend/src/components/MemoryBrowser.tsx`
- Test: `relio/frontend/tests/MemoryBrowser.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// tests/MemoryBrowser.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { MemoryBrowser } from "../src/components/MemoryBrowser";
import { searchMemory, addMemory } from "../src/api/client";

vi.mock("../src/api/client", () => ({
  searchMemory: vi.fn(),
  addMemory: vi.fn(),
  deleteMemory: vi.fn(),
}));

const rec = (id: string, content: string) =>
  ({ id, content, type: "semantic" }) as never;

test("searching renders result rows", async () => {
  (searchMemory as ReturnType<typeof vi.fn>).mockResolvedValue({
    results: [rec("mem_1", "apple pie recipe")],
    text: "- apple pie recipe",
  });
  const user = userEvent.setup();
  render(<MemoryBrowser user="you" />);
  await user.type(screen.getByLabelText("search"), "apple");
  await user.click(screen.getByRole("button", { name: "Search" }));
  expect(await screen.findByText("apple pie recipe")).toBeInTheDocument();
});

test("adding a memory calls addMemory then refreshes", async () => {
  (addMemory as ReturnType<typeof vi.fn>).mockResolvedValue(rec("mem_2", "new note"));
  (searchMemory as ReturnType<typeof vi.fn>).mockResolvedValue({ results: [], text: "" });
  const user = userEvent.setup();
  render(<MemoryBrowser user="you" />);
  await user.type(screen.getByLabelText("new memory"), "new note");
  await user.click(screen.getByRole("button", { name: "Add" }));
  expect(addMemory).toHaveBeenCalledWith("new note", { user: "you" });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio/frontend && npx vitest run tests/MemoryBrowser.test.tsx`
Expected: FAIL — cannot resolve `../src/components/MemoryBrowser`.

- [ ] **Step 3: Write the implementation**

```tsx
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
    await deleteMemory(id);
    setResults((r) => r.filter((x) => x.id !== id));
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd relio/frontend && npx vitest run tests/MemoryBrowser.test.tsx`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add relio/frontend/src/components/MemoryBrowser.tsx relio/frontend/tests/MemoryBrowser.test.tsx
git commit -m "feat: MemoryBrowser component"
```

---

### Task 6: Wire App + full styling + full-suite + build

**Files:**
- Modify: `relio/frontend/src/App.tsx`
- Modify: `relio/frontend/src/styles.css`
- Modify: `relio/frontend/tests/smoke.test.tsx`

- [ ] **Step 1: Update the smoke test to assert the two panes mount**

```tsx
// tests/smoke.test.tsx  (replace contents)
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import App from "../src/App";

vi.mock("../src/api/client", () => ({
  chatStream: vi.fn(async function* () {}),
  searchMemory: vi.fn().mockResolvedValue({ results: [], text: "" }),
  addMemory: vi.fn(),
  deleteMemory: vi.fn(),
}));

test("App renders brand, chat composer, and memory browser", () => {
  render(<App />);
  expect(screen.getByText("Relio")).toBeInTheDocument();
  expect(screen.getByLabelText("message")).toBeInTheDocument();
  expect(screen.getByLabelText("search")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd relio/frontend && npx vitest run tests/smoke.test.tsx`
Expected: FAIL — `App` doesn't render the composer/search yet.

- [ ] **Step 3: Wire App and complete the styles**

`src/App.tsx`:
```tsx
import { ChatView } from "./components/ChatView";
import { MemoryBrowser } from "./components/MemoryBrowser";

export default function App() {
  const user = "you";
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Relio</span>
        <span className="tagline">one memory for your AI app</span>
      </header>
      <main className="layout">
        <ChatView user={user} />
        <MemoryBrowser user={user} />
      </main>
    </div>
  );
}
```

Append to `src/styles.css`:
```css
.app { min-height: 100vh; display: flex; flex-direction: column; }
.topbar {
  display: flex; align-items: baseline; gap: 12px;
  padding: 16px 24px; border-bottom: 1px solid var(--line);
  background: var(--surface);
}
.tagline { color: var(--muted); font-size: 0.85rem; }
.layout {
  flex: 1; display: grid; grid-template-columns: 1fr 340px;
  gap: 20px; padding: 20px; max-width: 1100px; width: 100%; margin: 0 auto;
}
.chat, .browser {
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); display: flex; flex-direction: column;
  overflow: hidden;
}
.messages { list-style: none; margin: 0; padding: 16px; flex: 1; overflow-y: auto; }
.bubble {
  max-width: 80%; margin: 8px 0; padding: 10px 14px;
  border-radius: 12px; line-height: 1.45; white-space: pre-wrap;
}
.bubble.user { margin-left: auto; background: var(--accent); color: #fff; }
.bubble.assistant { margin-right: auto; background: var(--accent-soft); color: var(--ink); }
.composer { display: flex; gap: 8px; padding: 12px; border-top: 1px solid var(--line); }
.composer input, .search input, .add input {
  flex: 1; padding: 10px 12px; border: 1px solid var(--line);
  border-radius: 10px; font: inherit; background: var(--canvas);
}
button {
  padding: 10px 16px; border: none; border-radius: 10px;
  background: var(--accent); color: #fff; font: inherit; cursor: pointer;
}
button:disabled { opacity: 0.5; cursor: default; }
.browser { padding: 16px; gap: 12px; }
.browser-title { font-family: "Fraunces", serif; margin: 0; font-size: 1.1rem; }
.search, .add { display: flex; gap: 8px; }
.results { list-style: none; margin: 0; padding: 0; flex: 1; overflow-y: auto; }
.result {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 0; border-bottom: 1px solid var(--line);
}
.result-content { flex: 1; }
.chip {
  font-size: 0.7rem; color: var(--accent); background: var(--accent-soft);
  padding: 2px 8px; border-radius: 999px;
}
.result button { padding: 2px 9px; background: transparent; color: var(--muted); }
.error { color: #b4452f; margin: 0; }
```

> When implementing, use the **frontend-design** skill to refine the visual polish (spacing, typographic rhythm, micro-interactions) while keeping these tokens and the class names the tests rely on (`message`, `search`, `Send`, `Search`, `Add`, `results`).

- [ ] **Step 4: Run the full suite + build**

Run: `cd relio/frontend && npm test`
Expected: PASS — all test files green (smoke, client, ChatView, MemoryBrowser).

Run: `cd relio/frontend && npm run build`
Expected: Vite builds to `frontend/dist/` with no errors (verifies the whole app compiles).

- [ ] **Step 5: Commit**

```bash
git add relio/frontend/src/App.tsx relio/frontend/src/styles.css relio/frontend/tests/smoke.test.tsx
git commit -m "feat: wire App (chat + memory browser) with styling"
```

---

## Self-Review

**Spec coverage (frontend design doc):**
- Vite + React + TS scaffold + dev proxy → Task 0. ✅
- Typed API client (add/search/delete + SSE chat) → Tasks 1–3. ✅
- Streaming ChatView → Task 4. ✅
- MemoryBrowser (search/list/add/delete) → Task 5. ✅
- Two-pane App + distinctive styling → Task 6. ✅
- Vitest + Testing Library, client/fetch mocked, no live backend → all test tasks + Task 0 setup. ✅

**Deferred (not in this plan, by design):** OpenAPI→TS codegen, auth UI, settings panel, mobile/desktop shells, single-port DevOps layer.

**Type/name consistency:** `MemoryRecord`/`SearchResult` (Task 1) consumed by client (2–3) and MemoryBrowser (5). Client exports `addMemory`/`searchMemory`/`deleteMemory`/`chatStream` used by both components and the smoke mock (6). aria-labels/button names the tests query (`message`, `search`, `new memory`, `Send`, `Search`, `Add`) match the components exactly. SSE frame parsing in `chatStream` (3) matches the backend's `data: {"delta"|"done"|"error"}\n\n` format from the backend plan.

**Placeholder scan:** No TBD/TODO; every code step contains complete, runnable code.

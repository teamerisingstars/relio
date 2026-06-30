# Relio Memory — Unified AI Memory Engine (Project 1 Design)

**Date:** 2026-06-30
**Status:** Draft for review
**Name:** Relio Memory — the memory engine / flagship module of the **Relio** framework (verified free on PyPI + npm; repo at `github.com/relio-ai`)

---

## 1. Vision

Relio Memory is **one memory system that becomes the single storage an AI application
needs.** Today AI apps bolt together several stores — a vector DB for semantic
recall, a SQL/document DB for structured facts, a key-value cache for session
state, sometimes a graph DB for relationships. Relio Memory absorbs all four roles
into **one embedded, local-first engine** behind one simple API, so developers
stop wiring up 3–4 systems.

Because it is a single SQLite file with no server and no SaaS bill, it is also
the **cheapest possible** option, and because it ships an open record format and
an MCP server, it is positioned to become a **widely adopted standard** rather
than just another silo.

### Honest scope of the claim
No system is cheaper *and* faster *and* more accurate than every existing system
at once — those trade off. Relio Memory's defensible position is: **dramatically
cheaper and simpler for self-hosted AI-agent memory ("one thing instead of
four"), with a unified API that can wrap or replace existing stores.** That is
the target, not "best at everything."

### Relationship to the larger goal — Python + React, one port, one deploy
The end goal is the user's own framework whose **whole reason to exist** is that
it makes a **Python (FastAPI) backend + React frontend** build and deploy as a
**single unit** — one port, one command — so the developer using the framework
never manages two builds or two deploys. This is the product, not a workaround
(the proven category: Reflex for Python, Django/Rails bundling a built SPA).

- **Stack (decided): FastAPI (Python, MIT) backend + React frontend.** The
  memory engine is **embedded in-process inside FastAPI** (Python → no sidecar).
- **Framework-provided DevOps layer (the core value):** the framework generates
  and owns a **single deployable container** with a built-in **reverse proxy /
  single entrypoint** (e.g. Caddy, or FastAPI as router) that exposes **one
  port** and routes internally: `/api/*` → FastAPI, everything else → the React
  app. The framework ships the Dockerfile, proxy/router config, and process
  orchestration so the developer never wires this up.
- **One command for everything:** `relio dev` (both services on one URL with
  hot-reload), `relio build` (produces the one container/artifact), `relio
  deploy` (ships it to any host). The deployer sees one port, one command, one
  deploy.
- **Rendering is not constrained by this:** behind the reverse proxy the React
  frontend can be a **static SPA** *or* a **Node SSR server** — either way it is
  still one external port, one container, one deploy. Default leans SPA for
  simplicity; SSR is an opt-in the proxy already accommodates.
- **Honest footnote:** "one port / one command / one deploy" is exactly what the
  deployer experiences. Inside the one container there may be one or two
  processes (FastAPI, optionally a Node renderer) managed for them — invisible by
  design, which is precisely the framework's value. React is JavaScript, so a JS
  build step exists; the framework *orchestrates* it behind one command rather
  than eliminating it.
- **Licensing:** every layer is MIT/permissive; SQLite is public domain.
  Framework intended MIT (open = path to "widely accepted standard"). No
  from-scratch web/framework layers — the unique value is the memory DB.
- **Build order within the one project:** the storage core is implemented
  **first** because the backend and UI depend on memory that must exist before it
  can be wired up. One repo, one deploy, sensible order-of-operations.

This spec covers **only the memory engine (the core)** — an embeddable Python
library plus an MCP server. The FastAPI backend, the React frontend, and the
single-port DevOps layer are designed later, on top of it.

---

## 2. Core architecture

**One embedded engine, backed by SQLite, covering all four roles.** SQLite is a
single file, no server, no SaaS bill — the cheapest storage that exists — and it
can play all four roles at once:

| Role | Implementation |
|------|----------------|
| **Semantic (vectors)** | `sqlite-vec` extension stores embeddings + similarity search; quantization shrinks vectors |
| **Structured facts** | Plain SQL tables with native typed columns |
| **Session / working (KV)** | A key-value table with TTL / expiry |
| **Graph (relationships)** | `nodes` + `edges` tables with recursive traversal queries |

On top of the core sit three layers:

1. **Cost pipeline** — embedding cache + dedup (never pay to embed the same text
   twice), local embedding model by default (zero API cost), token-light recall
   (return tight, ranked NL lines so the LLM burns fewer tokens).
2. **Compatibility** — import/export adapters (mem0 / Letta / vector-DB formats
   → Relio Memory and back) for migration in and out.
3. **Adoption surface** — one clean Python API + an MCP server (so Claude and any
   MCP agent can use it instantly). This MCP seam is also where Project 2 plugs
   in.

---

## 3. The format (the standard)

There is **no widely-accepted standard format for AI memory today** — mem0,
Letta, and each vector DB have their own, and none covers all four roles. Relio Memory
defines **its own open, versioned format as a lossless superset** that can
import/export the others. This is what makes it a candidate standard rather than
another silo.

**Critical design point: "the format" is three boundaries, each optimized
separately — not one JSON blob everywhere.**

1. **On disk (fast + small):** native SQLite typed columns + quantized binary
   vector blobs. No JSON, no repeated keys ever persisted.
2. **Developer API (friendly):** plain typed Python objects (Pydantic). The dev
   writes one line, never a schema.
3. **LLM boundary (token-light):** memories render as **compact natural-language
   lines**, e.g. `- Alice works at Acme; prefers Python (pref, 0.9)`
   (~12 tokens) vs. the equivalent JSON record (~70+ tokens) — roughly **5× cheaper in tokens**, and the form LLMs parse best.

JSON (or a compact binary like MessagePack) appears in **exactly one place** —
the optional import/export interchange — never as the working format.

### The universal record (one shape, four roles)
The `type` field plus which fields are populated decide how a record behaves.
Defined as **typed Python code (Pydantic) for now**; formalized into a written
`SPEC.md` later once proven.

Conceptual fields (illustrative — not the on-disk layout):

- `id` — stable, globally unique
- `type` — `semantic | fact | session | node | edge`
- `content` — text that gets embedded (semantic recall)
- `data` — structured payload (facts / KV values)
- `relations` — `[{predicate, target_id}]` (graph edges)
- `scope` — `{user, agent, session}` partitioning
- `metadata` — `{source, tags, confidence, ...}`
- `ttl` — set for session/working memory; null = permanent
- `embedding_ref` — pointer into the vector index (not stored inline)
- `created_at`, `updated_at`, `schema_version`

### Key properties for adoptability
- **Open & versioned** (`schema_version`) — anyone can implement it.
- **Lossless superset** — holds everything the others hold; migration drops
  nothing.
- **Engine-agnostic** — the format is separate from SQLite; a Postgres backend
  later would still be "the same memory."

---

## 4. Components (small, independently testable units)

1. **Record model** — Pydantic schema for the universal record. *Defines the
   format.* Responsibility: validation, (de)serialization for interchange.
2. **Store core** — owns the SQLite connection and schema: typed columns for
   structured fields, `sqlite-vec` (Python binding) for vectors, KV table with
   TTL, `nodes`/`edges` for graph. Single-file, ACID. Responsibility: persistence
   + transactions.
3. **Embedding layer** — pluggable embedder interface; **local model default**
   (e.g. `fastembed` / sentence-transformers, zero API cost) + optional paid
   embedders; wrapped in **cache + dedup** keyed by content hash so identical
   text is embedded once. Responsibility: text → vector, cheaply.
4. **Recall engine** — hybrid query (vector similarity + structured filters +
   optional graph hop) → ranking → **token-light NL-line rendering** at the LLM
   boundary. Responsibility: question → ranked, token-minimal memories.
5. **Public API** — the one-line developer surface: `add`, `recall`, `get`,
   `forget`, `link`. Typed, friendly. Responsibility: ergonomics over the lower
   layers.
6. **Interchange** — import/export adapters (mem0 / Letta / vector-DB ↔ Relio Memory
   records). Responsibility: migration in and out; lossless where possible,
   reported where not.
7. **MCP server** — exposes `add` / `recall` (and friends) as MCP tools (MCP
   Python SDK). Responsibility: instant compatibility with Claude/any MCP agent;
   the seam the rest of the package plugs into.

Each unit answers: *what it does, how you use it, what it depends on.* Higher
units depend only on the public interfaces of lower ones (API → recall/store →
embedding → record model).

---

## 5. Data flow

**Write** — `add(text, scope, data?, ttl?)`:
1. Hash content → dedup check (skip embed if seen).
2. Embed via embedding layer (cache-aware); on embedder failure, enqueue
   "embed later" and still persist.
3. Write the record across the relevant SQLite tables in **one transaction**.
4. Return the typed record.

**Read** — `recall(query, scope, filters?, k?)`:
1. Embed the query (cache-aware).
2. Vector search + apply structured filters + optional graph hop.
3. Rank results.
4. Render to **compact NL lines**.
5. Return ranked, token-minimal memories.

---

## 6. Error handling

- **Atomicity:** all writes are single-file ACID transactions (free from
  SQLite); a partial write never corrupts state.
- **Embedder failures never hard-fail a write:** fall back to a "store now,
  embed later" queue; the record is retrievable by structured/KV/graph means
  immediately and gains semantic recall once embedded.
- **Imports are non-destructive:** corrupt or unmappable rows are **skipped and
  reported**, never silently dropped.
- **TTL:** expired session/working records are filtered on read and reaped
  lazily.

---

## 7. Testing strategy

Unit tests per component:
- Record validation + interchange round-trip.
- Store CRUD across all four roles; transaction atomicity.
- Dedup correctness (same text → one embedding).
- TTL expiry behavior.
- Graph traversal correctness.
- **Token-count assertion** on recall rendering (guards the "token-light" claim).

Integration:
- Round-trip import/export against a sample mem0 export (no data loss on the
  superset path; reported gaps where a source field has no Relio Memory home).
- End-to-end `add` → `recall` returns the expected memory under a realistic
  scope.

---

## 8. Explicitly out of scope (Project 1)

Deferred to later layers of the **same single package** (built on top of the
engine, in the same one-port/one-command deploy — not separate repos):
- FastAPI backend (Python) — embeds the engine in-process.
- React frontend + chat/agent UI kit.
- The framework DevOps layer: single container, reverse proxy / single entrypoint
  on one port, and the `relio dev` / `build` / `deploy` CLI.
- Hosted / multi-tenant mode, auth.
- Formal published written `SPEC.md` (format is code-defined for now).

For this spec, Relio Memory is delivered as an **embeddable Python library + MCP
server** — the core the rest of the package is built around.

---

## 9. Open decisions captured

| Decision | Choice |
|----------|--------|
| Memory type | AI/LLM agent memory **+** vector/embedding store (combined) |
| Compatibility meaning | Adapter layer **+** drop-in-friendly API **+** import/export |
| Cost targets | Embedding API, vector hosting, recall tokens, self-hosting — all (→ local-first) |
| Roles unified | Semantic + structured + session/KV + graph (all four) |
| Language | **Python** engine + FastAPI backend; **React** frontend |
| Format origin | Own open superset format |
| Format representation | Three boundaries: typed columns on disk / Pydantic API / NL-line recall |
| Spec status | Code-defined now, written spec later |
| Build/deploy | One port, one command, one deploy artifact — framework-provided DevOps layer (single container + reverse proxy) makes Python backend + React frontend deploy as one |
| Build order | One single package; storage core implemented first, backend/frontend/devops layered on top |
| Stack | FastAPI (Python) backend + React frontend; memory engine embedded in-process in FastAPI; reverse proxy unifies them on one port |
| Rendering | React as static SPA by default (simplest, one process); SSR opt-in via Node renderer behind the same proxy |
| Engine deps | `sqlite` + `sqlite-vec` (Python), `fastembed`/sentence-transformers (local embeddings), MCP Python SDK — all MIT; SQLite public domain |
| Licensing | All deps MIT/permissive (SQLite public domain); framework intended MIT — no from-scratch layers |
| Name | Relio Memory |
| Default embedder | Local model (zero cost), paid opt-in |

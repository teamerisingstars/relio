# Relio Architecture v2 — App-first, AI as a Called-in Component

**Date:** 2026-06-30
**Status:** Approved (decisions D1–D8); supersedes the memory-first framing in
`2026-06-30-relio-framework-architecture.md`
**Scope:** the architectural model the framework targets next. Implementation
follows the build order in §9, each step as its own spec → TDD.

---

## 1. The shift

v1 framed Relio as a **memory-first** framework: every app was assumed to be a
memory/chat app built *around* the engine. That is wrong for real products.

**v2 is app-first.** A developer builds **any** application on the FastAPI
backend + React frontend the framework provides, with their **own** data layer.
The AI/memory engine is **one component in the architecture, called into the
backend only where AI is needed.** AI is an opt-in capability, not the center of
gravity.

This dissolves the earlier ERP/CRM tension: you don't build the CRM *in* Relio —
you build a normal app and **call AI into it**.

### Core principle: one seamless system

The app, its data, the AI components, agents, and MCP must run as **one coherent
system** — a single deployable where everything integrates natively and
seamlessly. AI is woven in (called in-process where needed), never a bolted-on
external service. "Seamless" means a unified developer experience and runtime
coherence; it does **not** mean ungoverned — the exposure map (D3) still bounds
what the AI can reach.

---

## 2. Locked decisions

| # | Decision |
|---|----------|
| **D1** | **App-first** identity — AI is a called-in component, not the product. |
| **D2** | **`RelioAI` seam** — one injectable service composing the AI-system **components**: memory/RAG, embeddings, graph, model routing, tools/function-calling, **MCP (server + client)**, multimodal/extraction, agents/orchestration, caching, guardrails, observability. |
| **D3** | **Exposure map** — app DB private by default; AI reaches only a declared, **field-limited** set of operations; the map auto-publishes as MCP tools. |
| **D4** | **Agents are first-class bounded contexts** — own memory namespace + tool slice + config + session; global is opt-in. |
| **D5** | **Your data layer** — bring-your-own; the framework ships an **optional** ORM/Postgres template, never forced. |
| **D6** | **Multimodal + structured extraction** in scope — image/PDF input, file ingest, schema/tool-use output (e.g. PDF drawing → bill). |
| **D7** | **Storage/query efficiency** — Postgres **JSONB + GIN** and indexed hot columns for the query path. |
| **D8** | **Efficiency levers** — token-compact LLM I/O first, then recall caching and ANN vector index. |

---

## 3. Layered architecture (v2)

```
        ┌──────────────────────────────────────────────────────┐
        │  Developer's App  (one port, one in-process unit)      │
        │                                                        │
        │   React frontend ──► FastAPI backend                   │
        │                        │   - YOUR routes               │
        │                        │   - YOUR data layer (own DB)  │ ◄── system of record
        │                        │                               │
        │                        │   calls in WHERE AI is needed │
        │                        ▼                               │
        │              ┌───────────────────────┐                 │
        │              │   RelioAI component    │  (D2)           │
        │              │  recall remember embed │                 │
        │              │  chat  extract  agent  │                 │
        │              └───────────┬───────────┘                 │
        │                          │ operates ONLY through        │
        │                          ▼                               │
        │              ┌───────────────────────┐                 │
        │              │   Exposure map (D3)    │  registry of     │
        │              │  tools + field allow   │  callable ops    │
        │              └───────────┬───────────┘                 │
        │            ┌─────────────┴──────────────┐               │
        │            ▼                            ▼               │
        │   YOUR DB (private,           Relio memory store        │
        │   reachable only via map)     (vectors+graph+kv)        │
        └──────────────────────────────────────────────────────┘
                                   │
                                   ▼  same map, external transport
                          MCP server (D3) → external agents
```

Key property retained from v1: the backend calls `RelioAI` **in-process** — no
network hop. That is the efficiency story (see §7).

---

## 4. Components

### 4.1 The app (developer-owned)
- FastAPI routes, React pages, and a **business data layer** the developer owns
  (Postgres + an ORM is the blessed default; D5 ships an optional template).
- This DB is the **system of record** and is **private by default** — AI cannot
  touch it except through the exposure map.

### 4.2 `RelioAI` — the called-in AI system (D2)

AI here is **not** just chat/extract/agent — it is a system of composable
components the backend reaches for where needed. `RelioAI` exposes them as one
seam:

**Knowledge & retrieval**
- `recall` / `remember` — semantic memory (RAG retrieval over the store).
- `embed` — embeddings (batch-capable, K).
- `graph` — entity/relationship traversal (Feature C).

**Reasoning & generation**
- `chat` — the lean agent loop (LLM-optional, H).
- `extract(file_or_text, schema)` — structured + multimodal extraction (D6).
- model routing — pluggable `LLMProvider`s; per-call model/params selection.

**Tools & interop**
- `tools` — the exposure map: declared, field-limited function calling (D3).
- **MCP — first-class and two-way**: a **server** that publishes the exposure
  map to external agents, and a **client** that lets Relio agents consume
  external MCP servers/tools. MCP is a core component of the AI system, not an
  afterthought.

**Orchestration & agents**
- `agent(name, …)` — bounded agents (D4) and multi-step workflows composing the
  components above.

**Cross-cutting**
- caching (prompt / embedding / recall), guardrails & validation, and
  observability / eval (tracing, token accounting) wrap every call.

`RelioAI` composes the existing `Memory`, embedder, LLM provider, graph, and MCP
into one library object the developer mounts where needed — not a set of
pre-wired routes. The components are modular: use one (just `recall`) or many.

### 4.3 Exposure map — the governed DB↔AI bridge (D3)
The contract that lets AI use **some** app data and nothing else:
- **Callable registry** — declared operations the AI may invoke
  (`@ai.tool def lookup_part_price(part_no) …`). The "what to call" map.
- **Field allowlist** — which columns each exposed entity reveals
  (`ai.expose(part, fields=[…])`). Costs/PII/other tenants stay invisible.
- Unmapped data does not exist to the AI.
- The same map **auto-publishes as MCP tools**, so in-app agents and external
  agents share one governed surface.
- Composes with scope: a map entry is further filtered by the caller's
  tenant/user/agent.

### 4.4 Agents — bounded contexts (D4)
A first-class `Agent` bundles four isolations, instead of a loose scope tag:
- **Memory namespace** — `Scope(agent=…)`; recall/add/history scoped to it.
- **Tool slice** — its subset of the exposure map; can call nothing else.
- **Config** — own model, system prompt, token budget, extraction policy.
- **Session** — own transcript/history.

Default is **private**; access to a shared/global pool is **granted, never
automatic** (private-by-default, shared-by-permission). Built on top of §4.3.

### 4.5 Storage & efficiency (D7, D8)
- Postgres `doc` → **JSONB + GIN**, plus indexed columns for hot query fields —
  makes the structured-query path (Feature J) real at scale.
- Vectors stay packed binary (already correct).
- Efficiency levers, in priority: **token-compact LLM I/O**, recall caching,
  ANN index (HNSW/IVFFlat).

---

## 5. Request flows

**AI called into a business route (e.g. PDF drawing → bill):**
1. Developer's `POST /invoices/from-drawing` receives the file.
2. `ai.extract(file, schema=BillOfMaterials)` → vision/structured model (D6).
3. App applies pricing using `ai`-exposed map tools (`lookup_part_price`) + its
   own logic.
4. App saves the invoice in **its own DB** (system of record).
5. `ai.remember(...)` records the part/price/quote for future recall.

**Agent acting with isolation:**
1. `billing = ai.agent("billing", space=…, tools=[…], model=…)`.
2. `billing.run(...)` recalls only billing's namespace, calls only billing's
   tools — cannot see support's memory or the unmapped DB.

---

## 6. What changes from today

| Area | Today | v2 target |
|---|---|---|
| Positioning | memory-first; `create_app(memory, provider)` is the app | app-first; AI is mounted into the developer's app |
| AI surface | `Memory` + routes | unified `RelioAI` seam (D2) |
| DB↔AI | only Relio's own store | **exposure map** over the app's own DB (D3) |
| Agents | `Scope.agent` tag only | first-class bounded `Agent` (D4) |
| MCP | exposes only `add`/`recall` | publishes the exposure map (D3) |
| Extraction | text chat only | multimodal + structured (D6) |
| PG storage | `doc TEXT`, cast per query | JSONB + GIN + indexed columns (D7) |

Most of the engine is already a callable library, LLM-optional (H), with the
`agent` scope dimension — so this is **realignment, not a rewrite**.

---

## 7. Efficiency posture

The default is a **single, seamless system**: one deployable where the backend
calls the AI **in-process** — no network hop to a separate vector DB / cache /
model gateway. That in-process path is the efficiency baseline and the reason the
whole app runs as one coherent unit.

Modularity comes from clean **in-process seams** (`RelioAI`, exposure map,
pluggable `StorageBackend`, MCP). Those same seams are also the **scale-out
points**: any heavy component — a shared GPU embedding service, or a service
split for independent deploy — can be externalized behind the same interface when
load or org needs justify it. Distribution is an **available option, not a
default**: start as one seamless system, externalize a component only when it
earns it.

---

## 8. Open considerations (not foreclosed)

Heavier capabilities — a built-in relational/business data layer, richer query
(joins/aggregations), component externalization (microservices), real-time, or
analytics — are **not part of the core v2 scope** but are **not ruled out**.
Each can be added behind the existing seams (data layer, `StorageBackend`, MCP)
if a real product need justifies it, without breaking the
single-seamless-system default.

---

## 9. Build order

```
0. THIS doc                                   ← lock the model
1. RelioAI seam + reposition scaffold/create_app   (D1, D2)
2. Exposure map: tool registry + field allowlist + MCP publish   (D3)
3. Agents as bounded contexts (on the map)         (D4)
4. Multimodal + structured extraction (PDF→bill)   (D6)
5. Efficiency pass: JSONB+GIN, indexed columns, token-compact I/O, recall cache  (D7, D8)
```

Optional data-layer template (D5) lands alongside step 1.
Each step ships as its own spec + TDD, like A–K.

# ADR-001: Relio System Architecture — App-First, AI as a Called-In Component

**Status:** Accepted
**Date:** 2026-07-01
**Deciders:** Relio maintainer (product + architecture)
**Supersedes:** the earlier "AI-framework-first" framing (v1)
**Applies to:** Relio 0.1.5 and the 0.x line

---

## Context

Relio is an open-source AI-memory framework (Python/FastAPI backend + React
frontend, published to PyPI). It exists in a crowded field where most "AI
frameworks" ask the developer to build **inside** the framework: the app becomes
an agent graph, and the real application (its domain model, its database, its
routes) is second-class.

Dogfooding an app on top of Relio (`care-relio-app`) surfaced the opposite need:
developers already have — or want to build — a **normal application**. They want
AI to be a *component they call into*, operating over their data through a
governed seam, not a runtime their app must dissolve into. The forces at play:

- **Trust boundary.** The moment an LLM can touch the app database, prompt
  injection and over-broad tool access become the dominant risk. The AI must
  reach app data only through an explicit, auditable allowlist.
- **Substitutability.** Storage (SQLite vs Postgres), LLM provider (Claude /
  OpenAI / Gemini / none), and auth (anonymous / API-key / JWT / full accounts)
  all vary per deployment and must be swappable without touching app code.
- **Progressive disclosure.** A `pip install relio` + 10 lines should work
  offline with zero keys; scale (pgvector, OAuth, MCP) is opt-in via extras.
- **Open-core.** The seam that separates "framework" from "product built on the
  framework" must be a clean architectural line, not a licensing afterthought.
- **One seamless system.** MCP, chat, extraction, agents, exposure, and the web
  client are one coherent surface — AI is the *full* component set, not a chat box.

## Decision

Adopt an **app-first architecture** in which the application is the primary
system and AI is a **called-in component** reached through a single facade,
`RelioAI`. All AI access to application data is mediated by a governed
**exposure map** (tool allowlist + field projections). Every external dependency
(storage, LLM provider, auth, embeddings) sits behind a narrow seam so it can be
swapped per deployment.

```
        ┌──────────────────────────── the developer's app ────────────────────────────┐
        │  FastAPI routes · domain model · app DB · React client                        │
        │                                   │ calls in                                  │
        │                                   ▼                                           │
        │                             ┌───────────┐                                     │
        │       exposure map  ◀───────│  RelioAI  │───────▶  Memory engine (typed,      │
        │  (@ai.tool / ai.expose:     │  (facade) │          scoped: tenant/user/       │
        │   the AI↔app-data boundary) └─────┬─────┘          agent/session)             │
        └───────────────────────────────────┼───────────────────────────────────────────┘
                     seams (swappable):      │
       LLMProvider ── StorageBackend ── AuthHook ── Embedder
     Claude/OpenAI/    SQLite(default)/   anon/apikey/   deterministic/
     Gemini/Fake/none  Postgres+pgvector  jwt/accounts   fastembed
```

## Options Considered

### Option A: Framework-first (app lives inside the agent runtime) — *rejected*
The app is expressed as an agent/graph; the framework owns the event loop, and
the domain model is adapted to the framework's abstractions.

| Dimension | Assessment |
|-----------|------------|
| Complexity | High — every app concern is refracted through framework primitives |
| Cost | High migration cost; hard to adopt incrementally |
| Scalability | Bounded by the framework's runtime assumptions |
| Team familiarity | Low — a new mental model before any value is delivered |

**Pros:** Powerful for greenfield agent-native apps; framework can optimize globally.
**Cons:** Can't wrap an existing app; the DB/domain becomes second-class; the AI
trust boundary is implicit and therefore hard to audit; lock-in.

### Option B: App-first, AI as a called-in component (RelioAI facade) — *chosen*
The app owns its runtime, routes, and DB. `RelioAI` is instantiated and called
where needed. Data access is only via the exposure map.

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low at the edge — one facade; seams hide the rest |
| Cost | Incremental — drop it into an existing app; delete it cleanly |
| Scalability | Each seam scales independently (SQLite→Postgres, provider swap) |
| Team familiarity | High — it's a library call, not a paradigm |

**Pros:** Explicit, auditable AI↔data boundary; works with existing apps;
provider/storage/auth all swappable; clean open-core seam; testable offline
(`FakeProvider` / `provider="none"`).
**Cons:** The facade must resist becoming a god-object; discipline required to
keep capabilities *optional* rather than mandatory.

### Option C: Managed service (AI + memory behind a hosted API) — *deferred, not foreclosed*
Relio runs as a SaaS; apps call it over the network.

| Dimension | Assessment |
|-----------|------------|
| Complexity | Shifts to ops; simplest client |
| Cost | Recurring infra + trust/latency cost of leaving the app boundary |
| Scalability | Centralized scaling, but a shared-tenant blast radius |
| Team familiarity | High for the client; opaque internals |

**Pros:** Easiest consumption; natural paid tier.
**Cons:** Data leaves the app boundary; offline/self-host stories weaken; wrong
as the *default* for an open-source-first, trust-sensitive framework.
**Disposition:** A managed offering can be built **on top of** Option B later —
Option B's seams are exactly what a hosted tier would sit behind. Not chosen as
the core, not ruled out as a product.

## Trade-off Analysis

The central trade-off is **control vs. power**. Option A maximizes what the
framework can do *for* you at the cost of what you can do *around* it. Option B
inverts that: the framework does less globally but never gets in the way, and —
critically — makes the **AI↔app-data trust boundary a first-class, explicit
object** (the exposure map) rather than an emergent property of an agent graph.

For a framework whose adoption story is "open-source-first, drop it into the app
you already have, keep your data inside your boundary," the auditable seam is
worth more than global optimization. Option B also yields the cleanest
**open-core line**: the seams and facade are OSS; higher-value products
(managed hosting, advanced governance, vertical agents) attach at the seams
without forking the core.

Subsystem decisions that follow from the app-first choice:

| Seam | Decision | Rationale |
|------|----------|-----------|
| **Storage** | `StorageBackend` protocol; **SQLite + sqlite-vec default**, Postgres + pgvector (pooled, JSONB+GIN) for scale | Zero-config offline default; migrate only when scale demands. See ADR-002 (planned). |
| **LLM provider** | `LLMProvider` with **optional capabilities** (`extract` / `complete_with_tools` / `transcribe`) via `NotImplementedError`, not a mandatory interface; `make_provider(name)`, `"none"` disables | Providers differ in capability; capability negotiation stays duck-typed and lazy. `FakeProvider` makes the whole system testable offline. |
| **AI↔data boundary** | **Exposure map**: `@ai.tool` (allowlisted operations, `destructive=` gating) + `ai.expose(obj, fields)` (field projection) | The trust boundary is explicit and auditable; destructive tools are never auto-run by the agent loop. |
| **Agents** | `Agent` = a **bounded context** (a slice of tools + scope), autonomous tool-calling loop with a step cap | Blast radius is bounded by construction, not by prompt discipline. |
| **Auth** | `AuthHook = Callable[[Request], Scope]`: `anonymous` → `ApiKeyAuth` → `JWTAuth` → full `relio.accounts` | Pay-as-you-grow identity; `Scope` (tenant/user/agent/session) threads through memory + graph queries. |
| **Governance** | `relio check` gate (whole-word, case-insensitive stem matching) enforces test/doc coverage | Keeps generated + hand-written code honest without a heavy CI story. |
| **Packaging** | Optional extras (`local/mcp/postgres/server/jwt/accounts/openai/gemini/ai`); lazy client construction | Nothing is imported or keyed until used; install surface matches actual need. |

## Consequences

**Easier**
- Adopting Relio into an existing app (it's a call, not a rewrite).
- Auditing what the AI can touch (read the exposure map, not the whole app).
- Swapping storage/provider/auth per deployment and testing fully offline.
- Drawing the open-core line — products attach at seams.

**Harder**
- The `RelioAI` facade must be actively kept thin; capabilities must stay
  optional (the `transcribe`-as-`NotImplementedError` pattern is the template).
- Cross-cutting optimizations that a framework-first design gets "for free"
  (e.g. global agent scheduling) become the app's responsibility.
- Capability negotiation is duck-typed; a mismatched provider fails at call time,
  not construction time (mitigated by `FakeProvider` in tests).

**To revisit**
- **ADR-002 — Storage:** formal migration path + criteria for SQLite→Postgres.
- **ADR-003 — Exposure-map governance:** should capability negotiation move from
  duck-typed `NotImplementedError` to an explicit capability protocol/registry?
- **Managed tier (Option C):** revisit if/when a hosted product is on the roadmap;
  the seams are already positioned for it.

## Action Items

1. [x] Establish `RelioAI` facade as the single AI entry point (0.1.x).
2. [x] Ship exposure map (`@ai.tool` + `ai.expose`) with destructive-op gating.
3. [x] Land storage + provider + auth seams (SQLite/Postgres, Claude/OpenAI/Gemini/Fake, anon/apikey/jwt/accounts).
4. [ ] Write **ADR-002 (Storage backend strategy)** — migration triggers + data path.
5. [ ] Write **ADR-003 (Exposure-map governance & capability negotiation)**.
6. [ ] Add an architecture diagram + this ADR to the published docs site.
7. [x] Document the open-core boundary as an explicit seam inventory — see [open-core-seams.md](../open-core-seams.md).

# Open-Core Seam Inventory

> Companion to [ADR-001](adr/ADR-001-relio-system-architecture.md) (Action Item #7).
> This documents **where the open-core line falls** — which modules are the OSS
> core, and which seams a paid product would attach to — so the boundary is an
> architectural fact, not a licensing afterthought.

## Principle

Everything needed to **build a real app on Relio** is open source: the facade,
the memory engine, the storage/provider/auth seams, the governance gate, and the
scaffolds. Paid products don't fork the core — they **attach at the seams** the
core already exposes (`StorageBackend`, `LLMProvider`, `AuthHook`, the exposure
map, MCP). If a would-be paid feature requires editing a core module rather than
implementing a seam, that's a signal the seam is wrong, not that the feature
belongs in core.

## The core (OSS — always free)

| Module | Role | Why it's core |
|--------|------|---------------|
| `ai.py` (`RelioAI`) | The called-in AI facade | The entry point; must be free or nothing downstream works |
| `memory.py`, `recall.py`, `record.py`, `graph.py` | Typed, scoped memory + retrieval + graph | The substance of the framework |
| `embedding/` | Embedder seam (deterministic + `fastembed` local) | Needed to run offline with zero keys |
| `backends/` (`base`, `sqlite`, `postgres`) | `StorageBackend` seam + two impls | The storage seam itself is core; **specific hosted backends can be product-surface** |
| `exposure.py` | Exposure map (`@ai.tool`, `ai.expose`) | The AI↔data trust boundary — must be inspectable by everyone |
| `agents.py` | Bounded-context agent + tool-calling loop | Core agent primitive |
| `server/` (`app`, `auth`, `security`, `static`, `agent`) | FastAPI app factory, `AuthHook`, rate-limit, SPA mount | Batteries to ship an app |
| `server/llm/` | `LLMProvider` seam + Claude/OpenAI/Gemini/Fake + registry | Multi-provider is a core promise, not a paywall |
| `accounts/` | Password + OAuth user accounts | Table-stakes auth; keeping it free drives adoption |
| `mcp_server.py` | MCP interop | First-class interop is a core differentiator |
| `cli/` (`main`, `scaffold`, `check`) | `relio new/dev/build/check/deploy` + governance gate | The developer workflow |
| `interchange.py`, `sdkgen.py`, `render.py`, `aiapp/` | Import/export, SDK gen, rendering, app assembly | Glue that makes the core usable |

## The seams (where products attach)

Each seam is an interface the core defines and a paid product can implement
**without touching the core**:

| Seam | Core interface | Example product-surface (paid) attaching here |
|------|----------------|-----------------------------------------------|
| **Storage** | `StorageBackend` (ADR-002) | A managed/hosted vector store; a multi-region backend; a compliance-grade audited store |
| **LLM provider** | `LLMProvider` (ADR-003) | A routed/optimized provider (cost/latency routing); a fine-tuned domain model |
| **Auth / identity** | `AuthHook`, `relio.accounts` `UserStore` | SSO/SAML/SCIM enterprise identity; a hosted account service |
| **Exposure / governance** | exposure map + `relio check` | Advanced policy engine, audit logging, data-loss-prevention rules, approval workflows |
| **Agents** | `Agent` (bounded context) | Vertical prebuilt agents (domain packs) sold as products |
| **Deploy** | `relio deploy` | A managed hosting / control-plane (the ADR-001 Option-C managed tier) |
| **MCP** | `build_mcp_server` | Curated/hosted MCP tool catalogs |

## Boundary rules (how to keep the line clean)

1. **Core defines interfaces; products implement them.** A paid feature that
   can't be expressed as "implement seam X" doesn't belong on the other side of
   the line — fix the seam.
2. **No crippled core.** The OSS path must be genuinely production-viable
   (SQLite→Postgres, real auth, real providers). Paid = *scale / managed /
   enterprise-governance*, never *the basic feature, held back*.
3. **The trust boundary is always OSS.** The exposure map and governance gate are
   security-critical; they must be auditable by everyone, so they stay in core
   even though advanced *policies* on top can be product-surface.
4. **Seams are stable API.** Because products depend on them, `StorageBackend` /
   `LLMProvider` / `AuthHook` changes follow semver and get an ADR.

## Open questions

- Licensing mechanism (e.g. Apache-2.0 core + a separate commercial license for
  product modules) is **not decided here** — this doc fixes the *architectural*
  boundary; the license text is a separate decision.
- Whether "vertical agent packs" ship as separate installable extras or a
  marketplace is a go-to-market question, not an architecture one.

# Architecture Decision Records

Each ADR captures one significant architectural decision — the context, the
options weighed, the trade-off, and the consequences — so the *why* survives.

| # | Title | Status |
|---|-------|--------|
| [001](ADR-001-relio-system-architecture.md) | Relio system architecture — app-first, AI as a called-in component | Accepted |
| [002](ADR-002-storage-backend-strategy.md) | Storage backend strategy — SQLite default, Postgres for scale | Accepted |
| [003](ADR-003-provider-capability-negotiation.md) | LLM provider capability negotiation | Accepted |

## Conventions
- **Status:** Proposed → Accepted → (Deprecated / Superseded by ADR-NNN).
- One decision per record; number sequentially; never renumber. Supersede
  rather than delete.
- Keep the *options considered* even for the rejected ones — the rejected
  alternatives are the most useful part later.

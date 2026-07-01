# Relio

**App-first AI framework with a built-in, governed memory engine.**

You build a normal app; Relio's `RelioAI` is a *component you call into*. It
reaches your data only through a governed **exposure map**, remembers across
turns, and works offline with zero keys. AI is optional — add a provider when you
want chat, extraction, or autonomous tool-use.

```python
from relio import RelioAI

ai = RelioAI(path="relio.db")                 # local SQLite + local embeddings, no LLM needed
ai.remember("Alice manages the Acme account")
print(ai.recall("who manages Acme?")[0].content)
```

## Why Relio

- **App-first.** Drop it into an app you already have — it's a library call, not
  a paradigm. ([ADR-001](adr/ADR-001-relio-system-architecture.md))
- **Governed AI↔data boundary.** The AI can call only what you declare
  (`@ai.tool`) and see only the fields you allow (`ai.expose`). Destructive tools
  need explicit confirmation.
- **Swappable seams.** Storage (SQLite → Postgres+pgvector), LLM provider
  (Claude / OpenAI / Gemini / none), auth (anon → API-key → JWT → accounts) — all
  behind narrow interfaces.
- **Offline-testable.** `FakeProvider` + `DeterministicEmbedder` mean the whole
  system runs with no network and no keys.
- **One file, one container.** `relio new`, `relio dev`, `relio serve` — a
  scaffolded backend + React client on a single URL.

## Start here

- **[Getting started](getting-started.md)** — install, quickstart, scaffold an app.
- **[Structured query](querying.md)** — filter/rank records by metadata.
- **[Providers & capabilities](providers.md)** — choose a model; ask what it supports.
- **[Multi-tenancy & the exposure map](multi-tenancy.md)** — per-request scope, safe tools.
- **[Architecture (ADRs)](adr/README.md)** — the decisions and their trade-offs.

## Install

```bash
pip install "relio[server]"     # engine + FastAPI server + Claude provider
```

See [Getting started](getting-started.md) for the full extras matrix.

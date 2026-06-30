# Contributing to Relio

Thanks for working on Relio. This guide gets you from clone to green tests and
explains the conventions the codebase follows.

## Dev setup

Requires Python 3.11+.

```bash
git clone https://github.com/teamerisingstars/relio.git && cd relio
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                            # should be all green
```

`pyproject.toml` sets `pythonpath = ["."]`, so `pytest` finds the `relio`
package without any extra setup.

### Optional / gated tests
- **Postgres** integration tests are skipped unless a database is provided:
  ```bash
  RELIO_TEST_DATABASE_URL=postgresql://user:pass@localhost/relio_test pytest -m integration
  ```
  (Needs the `vector` extension available.)
- **Local embedding** model tests download a model; they're marked `integration`.

## How the project is built

Relio is developed **spec-first, test-first**:

1. **Design spec** — non-trivial work starts with a short spec under
   `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (goal, design, tests,
   what's out of scope).
2. **Tests first** — write the failing tests, then the implementation.
3. **Keep the suite green** — every change leaves `pytest` passing.

The architecture is described in
`docs/superpowers/specs/2026-06-30-relio-architecture-v2-app-first.md` — read it
before adding a component. The short version: the app is the developer's; the AI
engine is a **called-in component** (`RelioAI`); the DB is reached only through
the **exposure map**; agents are **bounded contexts**.

## Conventions

- **One concern per module.** When a file grows large, split it.
- **Match the surrounding code** — naming, comment density, idioms.
- **No new network hops.** The backend↔engine call is in-process by design; keep
  it that way unless a component genuinely must scale out behind a seam
  (`StorageBackend`, `AuthHook`, MCP).
- **Backends implement the full `StorageBackend` contract** (`add/get/delete/
  search/all/query/transaction/close`); add the matching SQLite **and** Postgres
  paths, with Postgres tests gated `integration`.
- **Identity comes from the auth hook**, never from request bodies.
- **Tests + docs for everything.** The framework ships a `relio check` gate that
  enforces this on scaffolded apps; hold the framework's own code to the same bar
  (a test for every module, a design spec for every feature).

## Layout

```
relio/ai.py            # RelioAI seam
relio/exposure.py      # exposure map (tool registry + field allowlist)
relio/agents.py        # bounded agents
relio/memory.py        # the engine (add/recall/history/query/graph/transaction)
relio/backends/        # sqlite.py, postgres.py (StorageBackend)
relio/embedding/       # base/local/cache (+ batch)
relio/server/          # app, routes (memory/chat/graph/history), auth, llm, agent
relio/cli/             # main, scaffold, check, dockerfile
relio/sdkgen.py        # OpenAPI -> TS + Python SDK
relio/templates/       # web / mobile / desktop scaffolds
tests/                 # mirrors the package; server tests under tests/server/
```

## Pull requests

- Reference or include the design spec for the change.
- Keep PRs focused; one feature/concern per PR.
- Run `pytest` (and `pytest -m integration` if you touched Postgres paths).
- Update the relevant doc/spec in the same PR.

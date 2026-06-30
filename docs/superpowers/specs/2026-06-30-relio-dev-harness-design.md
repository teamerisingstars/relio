# Step 6 — App Development Harness (dev mode, test mode, docs/instructions, gate)

**Date:** 2026-06-30
**Status:** Approved for implementation

## Goal

After scaffolding, the framework provides an **agentic development workflow** with
**built-in quality governance**: drive Claude Code to build the app, run tests,
keep instructions + docs in known places, and **ensure nothing exists without a
test and a doc**.

## Design

### CLI commands
- **`relio develop [prompt]`** — invokes the Claude Code CLI (`claude -p
  <prompt>`) in the project so the agent builds features under the framework's
  conventions. Shells out via the injected runner (graceful if `claude` absent).
- **`relio test`** — runs `pytest`; also `npm test` if a `web/` app exists.
- **`relio check`** — the governance gate (real logic, below). Exit code 1 on
  any violation.

### Governance gate — `relio/cli/check.py`
`check_project(root) -> list[Violation]`:
- Scans Python source under `root`, excluding `tests/ docs/ node_modules .git
  __pycache__ dist build .claude sdk` and `__init__.py`.
- Each module must be **referenced by a test** (a file under `tests/` mentioning
  the module stem) **and a doc** (a `.md` under `docs/` mentioning it).
- Returns `Violation(path, missing="test"|"doc")` for each gap.

### Instructions + documentation places (scaffolded)
`relio new` now also writes a **development harness** into the app:
- `CLAUDE.md` — the instructions: conventions, the test+doc rule, the RelioAI /
  exposure-map / agents patterns, the dev/test/check commands.
- `docs/README.md` + `docs/app.md` — documentation home.
- `tests/test_app.py` — a starter test.
- `.claude/settings.json` — a **Stop hook** running `relio check`, so an agentic
  session can't end with undocumented/untested code.

A fresh scaffold satisfies its own gate (`relio check` passes immediately).

## Extensions (implemented)

- **TypeScript/React gating** — `check_project` now also covers `.ts`/`.tsx`
  (excluding `.d.ts`, `*.test.*`/`*.spec.*`/`*.config.*`, and the generated
  `sdk/`). A TS module is "tested" by a co-located `*.test.tsx`/`*.spec.tsx` (or
  a `tests/` file) referencing its stem, "documented" by a `docs/*.md`. The web
  scaffold generates a presence test + a doc per component, and wires **vitest**
  (`npm test`), so a fresh web app passes its own gate.
- **Coverage thresholds** — `relio test --coverage --min N` runs
  `pytest --cov=. --cov-fail-under=N` (`pytest-cov` added to the dev extra).
- **Develop ↔ gate feedback loop** — `relio develop` runs `relio check` first and
  appends the current violations to the Claude Code prompt, so the agent closes
  test/doc gaps as it builds.

## Out of scope (YAGNI)

- Coverage of the TS side / doc-quality checks — presence gate only (+ Python
  coverage threshold).
- Managing Claude Code auth/install — assumed present for `relio develop`.

## Tests

- `check_project`: clean fixture (app.py + tests/test_app.py + docs/app.md) → no
  violations; remove the doc → one "doc" violation; remove the test → "test".
- `relio check` returns 0 when clean, 1 with violations.
- `relio develop "x"` runs `claude -p x`; `relio test` runs `pytest`.
- A freshly scaffolded app (base and web) **passes `check_project`**, and
  includes `CLAUDE.md`, `docs/`, `tests/`, `.claude/settings.json`.

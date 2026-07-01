# Releasing

Releases are **automatic**. To ship a version:

1. **Bump the version** in `pyproject.toml` to a final `X.Y.Z` (e.g. `0.1.6`).
   Keep `.dev0` / `rc` / `a` / `b` suffixes for work-in-progress — those are
   **not** published.
2. **Promote the changelog**: rename `## [Unreleased]` to `## [X.Y.Z] - <date>`
   in `CHANGELOG.md` (add a fresh empty `[Unreleased]` above it).
3. **Push to `main`.**

That's it. `.github/workflows/publish.yml` then:
- detects the version is a final `X.Y.Z` with no GitHub Release yet,
- builds + `twine check`,
- tags `vX.Y.Z` (force-moving a stale tag from a failed attempt),
- publishes to PyPI via OIDC Trusted Publishing (no stored token),
- creates the GitHub Release with the `[X.Y.Z]` changelog section as notes.

No manual tagging or release drafting. It's idempotent — if a release for the
version already exists it does nothing, so re-pushing is safe.

## Cadence

`release-reminder.yml` opens/bumps a "Release due" issue weekly when commits pile
up since the last tag. Ship regularly so users don't hit already-fixed bugs.

## Workflows (what runs when)

| Workflow | Trigger |
|----------|---------|
| `ci.yml` | push/PR — tests (SQLite + Postgres, coverage gate) **and** dependency audit |
| `publish.yml` | push to `main` touching `pyproject.toml` — auto-release (see above) |
| `docs.yml` | push to `main` touching `docs/` — deploy the docs site |
| `latest-deps.yml` | weekly — install newest deps, run suite (early breakage warning) |
| `release-reminder.yml` | weekly — nudge if unreleased commits pile up |

## Prerequisites (one-time)

- A PyPI **Trusted Publisher** for this repo: workflow **`publish.yml`**,
  environment **`pypi`**. (If you rename the workflow, update the publisher.)
- GitHub Pages enabled (source: `gh-pages` branch) for the docs site.

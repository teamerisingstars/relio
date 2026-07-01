# Releasing

Releasing is three steps — the CI does the rest (build, PyPI publish via Trusted
Publishing, GitHub Release with notes):

1. **Bump the version** in `pyproject.toml` (e.g. `0.1.6.dev0` → `0.1.6`).
2. **Promote the changelog**: rename `## [Unreleased]` to `## [0.1.6] - <date>`
   in `CHANGELOG.md` (add a fresh empty `[Unreleased]` above it).
3. **Tag and push**:
   ```bash
   git tag v0.1.6
   git push origin v0.1.6
   ```

`.github/workflows/publish.yml` then:
- guards that the tag (`v0.1.6`) matches the `pyproject.toml` version,
- builds + `twine check`,
- publishes to PyPI via OIDC Trusted Publishing (no stored token),
- creates the GitHub Release with the `[0.1.6]` changelog section as notes.

## Cadence

`release-reminder.yml` opens/bumps a "Release due" issue weekly when commits pile
up since the last tag. Publishing on a regular cadence is what keeps users from
hitting already-fixed bugs — don't let unreleased work accumulate for long.

## Prerequisites (one-time)

- A PyPI **Trusted Publisher** for this repo (owner/repo, workflow `publish.yml`,
  environment `pypi`).
- GitHub Pages enabled (source: `gh-pages` branch) for the docs site.

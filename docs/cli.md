# The `relio` CLI

The CLI is the main entry point to the framework. It's exposed two ways, both
dispatching to the same argument parser and handlers in `relio/cli/main.py`:

- the `relio` console script (declared in `pyproject.toml`), and
- `python -m relio`, via the `__main__` module (`relio/__main__.py`), which just
  calls `relio.cli.main:main` so `python -m relio ...` works without the script on
  PATH.

## Commands

| Command | Purpose |
|---------|---------|
| `relio new <name> [--web/--mobile/--desktop]` | scaffold an app (+ SDK + dev harness) |
| `relio ai new <name>` | scaffold an AI-first `AIApp` |
| `relio gui` | open Relio Studio (local control-panel GUI) |
| `relio dev` / `relio build` / `relio serve` | run/build/serve the app |
| `relio sdk` | generate TS + Python client SDKs |
| `relio deploy [--target]` | build a Docker image or write free-host deploy config |
| `relio dockerfile` | write the production Dockerfile |
| `relio test` / `relio check` | run tests / the governance gate |
| `relio migrate` | copy a memory store between backends |
| `relio develop` | drive Claude Code to build a feature |

Run `relio <command> --help` for the flags of any command.

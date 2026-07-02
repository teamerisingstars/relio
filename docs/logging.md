# Logging & the audit trail

Relio logs through the standard library under one tree — the `relio` logger and
per-subsystem children (`relio.server`, `relio.agents`, `relio.audit`, …).

Importing Relio attaches only a `NullHandler`, so it never emits "no handlers"
warnings and never configures logging behind your app's back. **You** decide what
to do with the logs.

## Turn logging on

```python
import relio
relio.configure_logging()                 # INFO to stderr
relio.configure_logging("DEBUG")           # more detail
relio.configure_logging(json=True)         # one JSON object per line (for log shippers)
```

Or drive it from the environment (no code):

```bash
export RELIO_LOG_LEVEL=DEBUG
export RELIO_LOG_JSON=1
```

`configure_logging()` is idempotent — calling it again replaces only the handler
it installed, never the ones your app added. If you already configure Python
logging yourself, just add handlers to `logging.getLogger("relio")` and skip it.

## The audit trail — `relio.audit`

Relio's trust boundary is the **exposure map**: the AI can only call tools you
declare. Every invocation through that boundary is logged to `relio.audit` with
structured context, so you have a compliance-grade trail of what the AI did and
on whose behalf.

| Field | Meaning |
|-------|---------|
| `tool` | tool name |
| `outcome` | `called` · `blocked` (destructive, unconfirmed) · `denied` (not in an agent's slice) |
| `destructive` | whether the tool is marked destructive |
| `tenant` / `user` / `agent` / `session` | the principal (from the injected `Scope`) |

```python
# Send the audit channel somewhere durable:
import logging
handler = logging.FileHandler("audit.log")
handler.setFormatter(relio.logs.JsonFormatter())
logging.getLogger("relio.audit").addHandler(handler)
```

Example (JSON) line for a blocked destructive call:

```json
{"level": "WARNING", "logger": "relio.audit", "message": "tool refund blocked (destructive, unconfirmed)",
 "tool": "refund", "outcome": "blocked", "destructive": true, "tenant": "acme", "user": "u_42"}
```

## Request logging (server)

```python
app = create_app(memory, provider, request_logging=True)
# logs "POST /api/chat -> 200 (12.4ms)" to relio.server.request
```

## Tune per subsystem

Because loggers are namespaced, you can raise or lower verbosity per area:

```python
logging.getLogger("relio.audit").setLevel(logging.INFO)   # keep the trail
logging.getLogger("relio.server").setLevel(logging.WARNING)  # quiet request noise
```

# Deploying Relio for free

A Relio app is a single Docker image that serves the API **and** the built
frontend on one port. That runs anywhere that runs a container. The one thing you
must not do on a free/stateless host is keep memory in a local SQLite file — the
disk is wiped between restarts. Relio's fix is a single knob: set `DATABASE_URL`
and memory moves to managed **Postgres + pgvector**.

## Why not Vercel / Netlify free?

Those free tiers run *stateless serverless functions*, not persistent servers:
no durable disk, short execution limits, and no long-lived process. Relio is a
stateful backend (memory + graph + vectors). So instead we deploy the container to
a free host that runs it as a real service.

## The three pieces

1. **A free Postgres** — [Neon](https://neon.tech) (generous free tier, has
   pgvector, doesn't expire) or Supabase. Copy its `postgres://…` URL. Relio's
   Postgres backend runs `CREATE EXTENSION IF NOT EXISTS vector` and creates its
   tables on first boot — no manual migration.
2. **A free container host** — Render (free web service), Fly.io (Docker-native),
   or a Hugging Face Docker Space.
3. **Secrets** — `DATABASE_URL`, `ANTHROPIC_API_KEY`, and `RELIO_EMBEDDER`.

Scaffolded apps are already deploy-ready: `app.py` reads `DATABASE_URL` from the
environment (Postgres in prod, SQLite locally) and `requirements.txt` includes the
`postgres` extra.

## Write a platform config

The CLI's `deploytargets` module backs `relio deploy --target`:

```bash
relio deploy --target render     # writes render.yaml (+ Dockerfile if missing)
relio deploy --target fly        # writes fly.toml
relio deploy --target hf         # prints the Hugging Face Space frontmatter
relio deploy                     # unchanged: builds the Docker image locally
```

Each config surfaces the env vars you must set as **secrets** on the platform
(never commit them). The command prints the exact next steps.

### Render (simplest free path)
1. `relio deploy --target render`, commit `render.yaml` + `Dockerfile`, push to GitHub.
2. In Render: **New + > Blueprint**, pick the repo.
3. Set `ANTHROPIC_API_KEY` and `DATABASE_URL` as secret env vars.
   (Free web services sleep when idle and cold-start on the next request.)

### Fly.io
1. `relio deploy --target fly`, then `fly launch --copy-config --no-deploy`.
2. `fly secrets set ANTHROPIC_API_KEY=… DATABASE_URL=…`
3. `fly deploy`.

### Hugging Face Space
Create a **Docker** Space, push the repo (prepend the printed frontmatter to your
`README.md`), and set the secrets under **Settings > Variables and secrets**.

## Serverless / "non-instance" hosting

Serverless platforms run stateless functions with no long-lived process. Relio can
run there, with three adjustments and one real trade-off:

1. **Pooled Postgres.** Use a connection-pooled `DATABASE_URL` (Neon's `-pooler`
   endpoint / PgBouncer) — many short-lived function instances otherwise exhaust
   connections.
2. **Hosted embedder.** `RELIO_EMBEDDER=openai` or `gemini` — the local model
   can't survive cold starts or fit a function bundle.
3. **An ASGI adapter**, generated for you (see below).

**The trade-off — streaming.** `POST /api/chat` streams via SSE, which serverless
proxies buffer or cut off at the function timeout. So on serverless, clients should
call the non-streaming **`POST /api/chat/complete`** (returns the whole reply as
one JSON `{"reply": …}`). The memory/graph/recall routes are plain JSON and work
unchanged.

```bash
relio deploy --target vercel    # writes api/index.py (ASGI) + vercel.json
relio deploy --target lambda    # writes lambda_handler.py (Mangum) + serverless.yml
relio deploy --target netlify   # writes netlify.toml (frontend + /api proxy)
```

- **Vercel** — `vercel` to deploy; set `DATABASE_URL` (pooled), `ANTHROPIC_API_KEY`,
  `RELIO_EMBEDDER` as Project env vars. The ASGI app serves both `/api` and the
  frontend.
- **AWS Lambda** — add `mangum` to `requirements.txt`, then `serverless deploy`.
  The Function URL supports response streaming if you later want it.
- **Netlify** — Netlify **doesn't run Python functions**, so it hosts the static
  frontend and proxies `/api/*` to a Relio backend deployed elsewhere (Vercel,
  Lambda, or a container). Set that backend host in `netlify.toml`.

## Choosing an embedder (`RELIO_EMBEDDER`)

The default local model downloads ~130MB and needs ~512MB RAM — too heavy for the
smallest free VMs. Options:

| Value | Cost | Notes |
|-------|------|-------|
| `openai` / `gemini` | API key | Hosted embeddings, tiny memory footprint — best for small free instances |
| `local` | free | ~130MB model; fine where RAM allows (e.g. Render free) |
| `deterministic` | free | Zero-dependency stand-in; **demo only**, recall quality is poor |

## From the GUI

Relio Studio's **Deploy** tab exposes the same targets: pick a name and target and
click Deploy — the generated config and next steps stream into the output panel.
See [studio.md](studio.md).

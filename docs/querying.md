# Structured Query (`query`)

`query()` filters records by **type**, **scope**, and **metadata** — the
non-semantic counterpart to `recall()` (which is vector search). It's exposed on
`Memory`, `RelioAI`, and `POST /api/memory/query`.

```python
ai.query(
    type=MemoryType.FACT,           # optional: filter by memory type
    scope=Scope(tenant="acme"),     # optional: restrict to a principal
    where={"roas__gte": 3.0},       # metadata filters (see below)
    order_by="-roas",               # sort by a metadata field ('-' = descending)
    limit=50,
    offset=0,
)
```

## `where` — metadata filters

Each key is a **metadata field name**, optionally suffixed with `__<operator>`.
Without a suffix the match is **exact equality**.

| Suffix | Meaning | Example | Value type |
|--------|---------|---------|------------|
| *(none)* | equals | `{"campaign": "c1"}` | any |
| `__gt` / `__gte` | greater (or equal) | `{"roas__gte": 3.0}` | number |
| `__lt` / `__lte` | less (or equal) | `{"spend__lt": 1000}` | number |
| `__ne` | not equal | `{"status__ne": "paused"}` | any |
| `__in` | membership | `{"campaign__in": ["c1", "c2"]}` | list |
| `__contains` | substring | `{"name__contains": "brand"}` | string |
| `__startswith` | prefix | `{"sku__startswith": "AB-"}` | string |

Rules:

- **Field-name form.** A key's field part must be a bare identifier (`\w+` —
  letters, digits, underscore). Dotted/nested paths and spaces are rejected to
  keep the stored JSON path safe. Store the value you want to filter on as a
  top-level metadata field.
- **Numeric comparisons** (`gt/gte/lt/lte`) compare numerically when the stored
  metadata value is a number. Store numbers as numbers (`{"roas": 3.2}`), not
  strings (`{"roas": "3.2"}`), or ranges won't order correctly.
- **Multiple keys** are ANDed together.
- Filters apply to `metadata`; use `type=`/`scope=` for those dimensions.

## `order_by`, `limit`, `offset`

- `order_by="field"` sorts ascending by a metadata field; `order_by="-field"`
  descending. Omit for insertion order (oldest first).
- `limit` (default 100) and `offset` page the result — `limit=20, offset=40` is
  the third page of 20.

## Example — rank campaigns by ROAS

```python
winners = ai.query(
    type=MemoryType.FACT,
    where={"roas__gte": 2.0, "status__ne": "paused"},
    order_by="-roas",
    limit=10,
)
```

To ingest such rows in one shot, `add_many` / `remember_many` accept mappings
with metadata:

```python
ai.remember_many([
    {"content": "Campaign c1 report", "type": MemoryType.FACT,
     "metadata": {"campaign": "c1", "roas": 3.2, "spend": 900, "status": "active"}},
    ...
])
```

## When to reach past `query()` — `sql()` (Postgres)

`query()` is for filtering/ranking records by a handful of metadata fields. For
heavy analytical workloads — joins, GROUP BY, window functions — use the **read-only
`sql()` escape hatch** on the Postgres backend. `query()` stays a thin, portable
filter; `sql()` is where analytics live.

```python
ai = RelioAI(memory=Memory(database_url="postgres://…"))

rows = ai.sql(
    "SELECT doc->'metadata'->>'campaign' AS campaign, "
    "       avg((doc->'metadata'->>'roas')::float) AS avg_roas "
    "FROM records GROUP BY campaign ORDER BY avg_roas DESC"
)
# [{"campaign": "c1", "avg_roas": 4.0}, ...]
```

Records live in `records(rid, id, doc JSONB, expires_at, embedding)`; pull fields
with `doc->>'content'`, `doc->'metadata'->>'roas'`, etc. (the `doc` column is
GIN-indexed). `sql()` allows a **single read-only** `SELECT`/`WITH` statement and
takes `params` for values — it is not available on SQLite (raises
`NotImplementedError`), which has no analytics path.
```

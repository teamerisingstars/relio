# Step 4 — Multimodal + Structured Extraction

**Date:** 2026-06-30
**Status:** Implemented (Claude vision path untested here — no API)
**Implements:** D6 of architecture v2.

## Goal

AI is not only chat: support reading a document/image (e.g. a PDF mechanical
drawing) and returning **structured** data (e.g. a bill of materials). This is
the capability that lets Relio participate in non-chat AI pipelines.

## Design

Extend the LLM provider contract with an optional `extract`:
- `LLMProvider.extract(prompt, schema=None, *, image_bytes=None, media_type=None)
  -> dict` — default raises `NotImplementedError` (optional capability).
- `FakeProvider.extract` — deterministic, offline: echoes source (text/image),
  media type, and the schema's field names. Makes wiring testable with no model.
- `ClaudeProvider.extract` — real call: builds an `image`/`document` content
  block (PDF → `document`), instructs JSON-only output for the schema, parses the
  response. Untested here (needs the API).

`RelioAI`:
- `extract(text, schema)` — text → structured.
- `extract_file(file, schema, media_type="application/pdf")` — bytes/path → reads
  the file, sends it as an image/PDF block → structured. Raises if no provider.

## Out of scope (YAGNI)

- Pydantic-model schemas (dict JSON-schema for now); validation of the returned
  dict against the schema.
- OCR fallbacks, multi-page chunking, layout parsing — the model handles the doc.

## Tests

- `extract(text, schema)` returns a dict with the schema's fields, source
  "text".
- `extract_file(bytes, schema)` returns source "image"/with media type.
- No provider → `RuntimeError`.
- A provider implementing only `stream` → `extract` raises
  `NotImplementedError`.

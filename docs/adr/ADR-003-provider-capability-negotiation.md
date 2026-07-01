# ADR-003: LLM Provider Capability Negotiation

**Status:** Accepted
**Date:** 2026-07-01
**Deciders:** Relio maintainer
**Relates to:** [ADR-001](ADR-001-relio-system-architecture.md) (the provider seam)

---

## Context

Relio talks to LLMs through the `LLMProvider` seam. Providers are unequal in what
they can do:

| Capability | Method | Claude | OpenAI | Gemini | Fake | none |
|------------|--------|:------:|:------:|:------:|:----:|:----:|
| Chat (required) | `stream` | ✓ | ✓ | ✓ | ✓ | — |
| Structured/vision extract | `extract` | ✓ | ✓ | ✓ | ✓ | — |
| Agent tool-calling | `complete_with_tools` | ✓ | ✓ | ✓ | ✓ | — |
| Speech-to-text | `transcribe` | — | ✓ (Whisper) | — | ✓ | — |

Only `stream` is `@abstractmethod`. The optional capabilities are declared on the
base class and **raise `NotImplementedError` by default**; a provider "has" a
capability by overriding the method. `make_provider(name)` builds providers
lazily and returns `None` for `"none"`. `RelioAI` guards with
`_require_provider(what)` (checks the provider *exists*) before delegating.

This works, but the capability contract is **implicit and discovered at call
time**. Two gaps:

1. **No way to ask before calling.** An app that wants to show/hide a "voice"
   button, or pick a provider that supports tools, must `try/except
   NotImplementedError` — there is no `provider.supports("transcribe")`.
2. **`_require_provider` checks existence, not capability.** Calling
   `ai.transcribe(...)` on a Claude provider passes the `None`-check and then
   fails deeper with `NotImplementedError` from the base method — a worse error,
   later, than a clear upfront "this provider can't transcribe."

## Decision (proposed)

Add **explicit, introspectable capability negotiation** while keeping the
duck-typed default as the fallback. Concretely:

1. A `capabilities()` method (or `CAPABILITIES` set) on `LLMProvider` returning
   the set of supported optional capabilities, defaulting to whatever the
   provider actually overrides.
2. A `supports(capability: str) -> bool` helper on the base class.
3. `RelioAI._require_provider(what)` upgraded to `_require_capability(what)`:
   raise a clear, early `CapabilityError` (`"the '<provider>' provider does not
   support <capability>"`) instead of letting the base `NotImplementedError`
   surface from deep in the call.

The default `capabilities()` is derived automatically (a method is "supported" if
the subclass overrides it), so **existing providers need no changes** and the
`NotImplementedError` contract still holds for anyone who bypasses the helper.

## Options Considered

### Option A: Status quo — implicit, `NotImplementedError` at call time — *rejected as the end state*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Lowest (nothing to build) |
| Cost | Paid by every caller as `try/except` and late failures |
| Scalability | Poor — more capabilities = more implicit contract |
| Team familiarity | High (plain Python) |

**Pros:** Zero code; already shipped.
**Cons:** Can't introspect; failures are late and deep; UI can't pre-flight;
`_require_provider` gives a false "OK" for unsupported capabilities.

### Option B: Derived `capabilities()` + `supports()` + capability-aware guard — *chosen (proposed)*
| Dimension | Assessment |
|-----------|------------|
| Complexity | Low — one method + one helper; default is auto-derived |
| Cost | Small, one-time; no per-provider churn |
| Scalability | Good — new capability = one method + one registry entry |
| Team familiarity | High |

**Pros:** Introspectable (`supports`); early, clear errors; backward-compatible
(auto-derived default); UI/agent can pre-flight; keeps duck-typing as fallback.
**Cons:** A second source of truth (method presence vs. declared set) unless the
default is auto-derived — which the decision requires, closing that gap.

### Option C: Full formal capability protocol (typed interfaces per capability) — *deferred*
Split capabilities into separate `Protocol`s (`SupportsTranscribe`, …) and use
`isinstance`/structural typing.
| Dimension | Assessment |
|-----------|------------|
| Complexity | Higher — a type hierarchy + mypy story |
| Cost | Real refactor; more concepts |
| Scalability | Excellent, statically checkable |
| Team familiarity | Medium |

**Pros:** Static guarantees; IDE knows what a provider can do.
**Cons:** Overkill for 3 optional capabilities; heavier than the problem;
Option B can evolve into this later if the capability count grows.

## Trade-off Analysis

The choice is **how much structure to add for how much introspection**. Option A
underserves callers (no pre-flight, late errors). Option C over-serves a
3-capability surface with a type hierarchy. Option B lands in the middle: it makes
capabilities *askable* and failures *early and legible*, at the cost of one method
and one helper — and by **auto-deriving** the default capability set from actual
method overrides, it avoids the classic "the declared list drifts from reality"
bug. If the capability surface grows substantially (say, tools/vision/audio/
video/embeddings all optional and independently varying), Option C becomes the
natural next step and Option B's `supports()` is forward-compatible with it.

Non-goal: this ADR does **not** change the `"none"` provider semantics
(`make_provider` still returns `None`, and `_require_provider`'s existence check
stays as the first gate) — capability negotiation is layered *after* the
"is there a provider at all?" check.

## Consequences

**Easier**
- Apps/UI can pre-flight: `if ai.provider.supports("transcribe"): show_mic()`.
- Failures become early and specific (`CapabilityError` at the seam, not a deep
  `NotImplementedError`).
- Choosing a provider by requirement (e.g. "needs tools") is a set membership check.

**Harder**
- One more concept in the provider contract (kept minimal + auto-derived).
- Must ensure the derived default and any explicit declaration can't disagree
  (the decision mandates auto-derivation as the single source of truth).

**To revisit**
- Escalate to Option C (typed per-capability protocols) if optional capabilities
  multiply or need static checking.
- ~~Whether `make_provider` should accept a `requires=[...]` list~~ — done
  (Action Item #4); revisit only if it needs richer matching (e.g. "any of").

## Action Items

1. [x] Add `LLMProvider.capabilities()` (auto-derived from overridden methods) + `supports(name)`.
2. [x] Introduce `CapabilityError`; upgrade `RelioAI._require_provider` → capability-aware guard for `extract` / `complete_with_tools` / `transcribe` (agent loop guards `complete_with_tools` too).
3. [x] Expose `RelioAI.supports(capability)` passthrough for app/UI pre-flight.
4. [x] `make_provider(name, requires=[...])` validates capabilities at build time — fails fast with `CapabilityError` (including when the provider is `"none"`).
5. [x] Tests: `Fake` reports all three optionals; `Gemini` reports no `transcribe` (OpenAI does); `ai.transcribe`/`ai.extract` on an unsupported provider raise `CapabilityError` early.
6. [x] Document the capability matrix (the table above) in the providers doc — see [providers.md](../providers.md).

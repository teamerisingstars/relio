# relio/exposure.py
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional


# A tool parameter named `scope` is reserved: it's injected per-call with the
# current principal's Scope, and hidden from the LLM-facing parameter schema — so
# a single registered tool serves every tenant instead of being closure-bound to
# one. The LLM never sees or controls it.
_RESERVED_PARAMS = {"scope"}


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., Any]
    description: str
    parameters: dict[str, str]  # param name -> type name (LLM-facing; excludes reserved)
    destructive: bool = False   # requires explicit confirm=True to run
    wants_scope: bool = False    # fn declares a `scope` param → inject per-call


def _param_schema(fn: Callable[..., Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, p in inspect.signature(fn).parameters.items():
        if name == "self" or name in _RESERVED_PARAMS:
            continue
        ann = p.annotation
        if ann is inspect.Parameter.empty:
            out[name] = "any"
        else:
            out[name] = getattr(ann, "__name__", str(ann))
    return out


def _wants_scope(fn: Callable[..., Any]) -> bool:
    return "scope" in inspect.signature(fn).parameters


class ExposureMap:
    """The declared surface the AI may use against the app's data.

    A registry of callable operations + a field allowlist helper. Anything not
    registered/exposed is invisible to the AI.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def tool(
        self,
        fn: Optional[Callable[..., Any]] = None,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        destructive: bool = False,
    ):
        """Register a callable as an AI-invokable tool. Usable bare or with args.

        `destructive=True` marks a tool that mutates/deletes/spends; it then
        requires an explicit `confirm=True` to run — a guard against a
        prompt-injected agent triggering it.
        """

        def register(f: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or f.__name__
            self._tools[tool_name] = ToolSpec(
                name=tool_name,
                fn=f,
                description=description or (f.__doc__ or "").strip(),
                parameters=_param_schema(f),
                destructive=destructive,
                wants_scope=_wants_scope(f),
            )
            return f

        return register(fn) if fn is not None else register

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"no such tool: {name!r}")
        return self._tools[name]

    def call(self, name: str, *, scope: Any = None, confirm: bool = False, **kwargs: Any) -> Any:
        spec = self.get(name)
        if spec.destructive and not confirm:
            raise PermissionError(
                f"tool {name!r} is destructive; call with confirm=True to run it"
            )
        if spec.wants_scope:
            kwargs["scope"] = scope  # per-request principal, injected — not LLM-supplied
        return spec.fn(**kwargs)

    @staticmethod
    def project(obj: Any, fields: list[str]) -> dict[str, Any]:
        """Field allowlist: keep only `fields`. Everything else stays invisible."""
        if isinstance(obj, dict):
            return {k: obj[k] for k in fields if k in obj}
        return {k: getattr(obj, k) for k in fields if hasattr(obj, k)}

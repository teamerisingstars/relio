# relio/exposure.py
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., Any]
    description: str
    parameters: dict[str, str]  # param name -> type name


def _param_schema(fn: Callable[..., Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, p in inspect.signature(fn).parameters.items():
        if name == "self":
            continue
        ann = p.annotation
        if ann is inspect.Parameter.empty:
            out[name] = "any"
        else:
            out[name] = getattr(ann, "__name__", str(ann))
    return out


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
    ):
        """Register a callable as an AI-invokable tool. Usable bare or with args."""

        def register(f: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or f.__name__
            self._tools[tool_name] = ToolSpec(
                name=tool_name,
                fn=f,
                description=description or (f.__doc__ or "").strip(),
                parameters=_param_schema(f),
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

    def call(self, name: str, **kwargs: Any) -> Any:
        return self.get(name).fn(**kwargs)

    @staticmethod
    def project(obj: Any, fields: list[str]) -> dict[str, Any]:
        """Field allowlist: keep only `fields`. Everything else stays invisible."""
        if isinstance(obj, dict):
            return {k: obj[k] for k in fields if k in obj}
        return {k: getattr(obj, k) for k in fields if hasattr(obj, k)}

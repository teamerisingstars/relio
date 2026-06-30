# tests/test_exposure.py
import pytest

from relio import RelioAI
from relio.embedding.base import DeterministicEmbedder
from relio.exposure import ExposureMap
from relio.memory import Memory


def _ai(tmp_path):
    m = Memory(path=str(tmp_path / "x.db"), embedder=DeterministicEmbedder(dim=16))
    return RelioAI(memory=m)


def test_tool_registration_and_catalog(tmp_path):
    ai = _ai(tmp_path)

    @ai.tool
    def lookup_part_price(part_no: str) -> float:
        """Return the list price for a part."""
        return {"AB-1": 9.99}.get(part_no, 0.0)

    catalog = ai.list_tools()
    assert len(catalog) == 1
    entry = catalog[0]
    assert entry["name"] == "lookup_part_price"
    assert "list price" in entry["description"]
    assert entry["parameters"] == {"part_no": "str"}
    ai.close()


def test_call_tool_invokes_and_unknown_raises(tmp_path):
    ai = _ai(tmp_path)

    @ai.tool
    def add_one(n: int) -> int:
        return n + 1

    assert ai.call_tool("add_one", n=41) == 42
    with pytest.raises(KeyError):
        ai.call_tool("missing")
    ai.close()


def test_expose_field_allowlist_drops_private_fields(tmp_path):
    ai = _ai(tmp_path)

    class Part:
        number = "AB-1"
        list_price = 9.99
        cost = 4.10  # private — must not leak

    projected = ai.expose(Part(), fields=["number", "list_price"])
    assert projected == {"number": "AB-1", "list_price": 9.99}
    assert "cost" not in projected

    d = {"number": "AB-1", "cost": 4.10}
    assert ai.expose(d, fields=["number"]) == {"number": "AB-1"}
    ai.close()


def test_map_publishes_as_mcp_tools(tmp_path):
    pytest.importorskip("mcp")
    ai = _ai(tmp_path)

    @ai.tool
    def part_status(part_no: str) -> str:
        return "in_stock"

    _server, tools = ai.mcp_server(include_tools=True)
    assert "part_status" in tools          # exposure-map tool published
    assert "add" in tools and "recall" in tools  # plus the memory tools
    assert tools["part_status"](part_no="AB-1") == "in_stock"
    ai.close()

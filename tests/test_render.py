# tests/test_render.py
from relio.render import render_lines
from relio.record import MemoryRecord, MemoryType


def test_renders_compact_lines_without_json_braces():
    records = [
        MemoryRecord(type=MemoryType.FACT, content="works at Acme",
                     metadata={"tags": ["pref"], "confidence": 0.9}),
        MemoryRecord(content="prefers Python"),
    ]
    text = render_lines(records)
    lines = text.splitlines()
    assert lines[0] == "- works at Acme (pref, 0.9)"
    assert lines[1] == "- prefers Python"
    assert "{" not in text and '"' not in text   # not JSON


def test_empty_input_renders_empty_string():
    assert render_lines([]) == ""


def test_rendered_line_is_far_shorter_than_json():
    r = MemoryRecord(type=MemoryType.FACT, content="works at Acme",
                     metadata={"tags": ["pref"], "confidence": 0.9})
    line = render_lines([r])
    assert len(line) < len(r.model_dump_json()) / 2   # token-light proxy

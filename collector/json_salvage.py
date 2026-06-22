"""Tolerant recovery of JSON objects from a (possibly truncated) LLM array response.

Reasoning models can overrun the token budget and cut a long `{"guides":[ ... ]}` payload off
mid-object, breaking strict json.loads. `iter_array_objects` salvages every COMPLETE object that
made it through, so a truncated/garbled tail costs only the last (incomplete) item, not the whole
batch. Pure, fully offline-testable.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any


def iter_array_objects(text: str, key: str) -> Iterator[dict[str, Any]]:
    """Yield each complete top-level ``{...}`` object inside the JSON array ``"key": [ ... ]``,
    stopping at the first incomplete/garbled object (or the array's end)."""
    marker = text.find(f'"{key}"')
    if marker == -1:
        return
    start = text.find("[", marker)
    if start == -1:
        return

    depth = 0
    in_str = False
    esc = False
    obj_start = -1
    for i in range(start + 1, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and obj_start >= 0:
                try:
                    yield json.loads(text[obj_start : i + 1])
                except json.JSONDecodeError:
                    return
                obj_start = -1
        elif c == "]" and depth == 0:
            return

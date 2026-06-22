"""Offline tests for tolerant JSON-array object recovery (pure)."""

from collector.json_salvage import iter_array_objects


def test_recovers_complete_objects_from_truncated_array():
    text = '{"guides":[{"a":1},{"b":2},{"c":'  # third object cut off
    assert list(iter_array_objects(text, "guides")) == [{"a": 1}, {"b": 2}]


def test_full_array_round_trips():
    assert list(iter_array_objects('{"guides":[{"a":1},{"b":2}]}', "guides")) == [
        {"a": 1},
        {"b": 2},
    ]


def test_braces_inside_strings_are_not_counted():
    text = '{"guides":[{"s":"a } { b"},{"t":2}]}'
    assert list(iter_array_objects(text, "guides")) == [{"s": "a } { b"}, {"t": 2}]


def test_nested_objects_and_truncated_tail():
    text = '{"guides":[{"x":{"y":1}},{"z":2'  # second object cut off
    assert list(iter_array_objects(text, "guides")) == [{"x": {"y": 1}}]


def test_missing_key_or_garbage_yields_nothing():
    assert list(iter_array_objects('{"other":[1]}', "guides")) == []
    assert list(iter_array_objects("not json at all", "guides")) == []

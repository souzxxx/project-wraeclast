"""Offline tests for multi-turn message assembly (pure — no DB/LLM)."""

from api.rag import _MAX_HISTORY_TURNS, build_messages


def _roles(messages):
    return [m["role"] for m in messages]


def test_empty_history_is_system_context_question():
    msgs = build_messages("CTX", "best farm?")
    assert _roles(msgs) == ["system", "user", "user"]
    assert "CTX" in msgs[1]["content"]
    assert msgs[-1]["content"] == "best farm?"


def test_history_threaded_in_order_between_context_and_question():
    history = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    msgs = build_messages("CTX", "q2", history)
    assert _roles(msgs) == ["system", "user", "user", "assistant", "user"]
    assert "CTX" in msgs[1]["content"]  # retrieved context lives in the preface
    # prior turns replayed verbatim, in order, after context and before the new question
    assert [m["content"] for m in msgs[2:]] == ["q1", "a1", "q2"]


def test_bounds_to_last_n_turns():
    history = [{"role": "user", "content": f"m{i}"} for i in range(_MAX_HISTORY_TURNS + 4)]
    msgs = build_messages("CTX", "now", history)
    replayed = [m["content"] for m in msgs if m["content"].startswith("m")]
    assert len(replayed) == _MAX_HISTORY_TURNS
    assert replayed[-1] == f"m{_MAX_HISTORY_TURNS + 3}"  # kept the most recent


def test_skips_invalid_roles_and_empty_content():
    history = [
        {"role": "system", "content": "should be dropped"},
        {"role": "user", "content": "   "},
        {"role": "assistant", "content": "kept"},
    ]
    msgs = build_messages("CTX", "q", history)
    assert _roles(msgs) == ["system", "user", "assistant", "user"]
    assert msgs[2]["content"] == "kept"


def test_question_is_always_last():
    history = [{"role": "assistant", "content": "earlier"}]
    msgs = build_messages("CTX", "the question", history)
    assert msgs[-1] == {"role": "user", "content": "the question"}

"""Tests for the RAG prompt assembler (build_context_block) — the chat's grounding."""

from api.rag import RagContext, build_context_block


def _ctx(**over):
    base = dict(
        chunks=[{"title": "Omens", "content": "Whittling removes the lowest-ilvl mod."}],
        farms=[{"name": "Abyss", "est_profit_per_hour": 30, "risk": "low"}],
        my_snapshot={"character_name": "Yuki", "char_class": "Monk", "level": 92},
        prices=[{"name": "Divine Orb", "divine_value": 1.0}],
        craft_methods=[],
    )
    base.update(over)
    return RagContext(**base)


def test_renders_knowledge_farms_snapshot_and_prices():
    block = build_context_block(_ctx())
    assert "Omens" in block          # community knowledge
    assert "Abyss" in block          # farms
    assert "Yuki" in block           # owner character
    assert "Divine Orb" in block     # prices


def test_priced_craft_method_shows_roi_unpriced_shows_missing():
    block = build_context_block(_ctx(craft_methods=[
        {"name": "Belt", "mechanics": ["currency"], "output": "belt", "priced": True,
         "roi_pct": 8980, "expected_cost_div": 0.03, "success_prob": 0.4, "missing_prices": []},
        {"name": "Omen craft", "mechanics": ["omen"], "output": "x", "priced": False,
         "roi_pct": None, "expected_cost_div": None, "success_prob": 0.5,
         "missing_prices": ["Omen of Whittling"]},
    ]))
    assert "Belt" in block and "ROI ~8980%" in block
    assert "not yet priceable" in block and "Omen of Whittling" in block

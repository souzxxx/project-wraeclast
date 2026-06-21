from collector.config import Settings
from collector.ninja_client import normalize_exchange

SAMPLE = {
    "core": {"primary": "divine", "secondary": "exalted", "items": [], "rates": {}},
    "lines": [
        {"id": "alch", "primaryValue": 0.0024},
        {"id": "chaos", "primaryValue": 0.01},
        {"id": "nameless"},  # no matching item -> skipped
    ],
    "items": [
        {"id": "alch", "name": "Orb of Alchemy", "category": "Currency"},
        {"id": "chaos", "name": "Chaos Orb", "category": "Currency"},
    ],
}


def test_normalize_exchange_zips_lines_and_items_by_id():
    rows = normalize_exchange(SAMPLE, "Runes of Aldur")
    by_name = {r.name: r for r in rows}
    assert set(by_name) == {"Orb of Alchemy", "Chaos Orb"}
    assert by_name["Orb of Alchemy"].divine_value == 0.0024
    assert by_name["Orb of Alchemy"].item_type == "currency"
    assert by_name["Orb of Alchemy"].league == "Runes of Aldur"


def test_normalize_exchange_uses_primary_currency_for_column():
    rows = normalize_exchange(SAMPLE, "Runes of Aldur")
    # core.primary == "divine" -> value goes in divine_value, chaos_value stays None
    assert all(r.chaos_value is None for r in rows)
    assert all(r.divine_value is not None for r in rows)


def test_normalize_exchange_handles_empty_and_missing():
    assert normalize_exchange({}, "Runes of Aldur") == []
    assert normalize_exchange({"core": {}, "lines": None, "items": None}, "L") == []


def test_normalize_exchange_chaos_primary():
    payload = {
        "core": {"primary": "chaos"},
        "lines": [{"id": "x", "primaryValue": 5}],
        "items": [{"id": "x", "name": "Thing"}],
    }
    rows = normalize_exchange(payload, "L")
    assert rows[0].chaos_value == 5
    assert rows[0].divine_value is None


def test_normalize_exchange_tags_custom_item_type():
    # the same parser serves every craft-surface category — it just gets a different item_type
    rows = normalize_exchange(SAMPLE, "L", item_type="essence")
    assert rows and all(r.item_type == "essence" for r in rows)


def test_ninja_economy_category_list_parses_pairs():
    s = Settings(ninja_economy_types="Currency:currency, Essences:essence ,Ritual:ritual,, Bare")
    assert s.ninja_economy_category_list == [
        ("Currency", "currency"),
        ("Essences", "essence"),
        ("Ritual", "ritual"),
        ("Bare", "currency"),  # no ':' -> defaults to currency
    ]

"""Offline tests for the bench currency-price projection (pure — no DB)."""

from api.prices import currency_prices


def _row(name, item_type="currency", chaos=1.0, divine=0.01):
    return {"name": name, "item_type": item_type, "chaos_value": chaos, "divine_value": divine}


def test_keeps_only_currency_rows():
    rows = [_row("Exalted Orb"), _row("Some Tablet", item_type="tablet"), _row("Divine Orb")]
    out = currency_prices(rows)
    assert [p["name"] for p in out] == ["Exalted Orb", "Divine Orb"]


def test_projects_only_needed_fields():
    [p] = currency_prices([_row("Chaos Orb", chaos=3.0, divine=0.03)])
    assert p == {"name": "Chaos Orb", "chaos_value": 3.0, "divine_value": 0.03}


def test_drops_nameless_rows():
    rows = [{"item_type": "currency", "chaos_value": 1.0}, _row("Regal Orb")]
    assert [p["name"] for p in currency_prices(rows)] == ["Regal Orb"]


def test_tolerates_missing_values():
    [p] = currency_prices([{"name": "Vaal Orb", "item_type": "currency"}])
    assert p["chaos_value"] is None and p["divine_value"] is None

from collector.ninja_client import normalize_currency, normalize_items


def test_normalize_currency_classic_shape():
    payload = {
        "lines": [
            {"currencyTypeName": "Divine Orb", "chaosEquivalent": 250.5, "listingCount": 40},
            {"currencyTypeName": "Exalted Orb", "chaosEquivalent": 12},
        ]
    }
    rows = normalize_currency(payload, "test-league")
    assert len(rows) == 2
    assert rows[0].name == "Divine Orb"
    assert rows[0].chaos_value == 250.5
    assert rows[0].item_type == "currency"
    assert rows[0].league == "test-league"


def test_normalize_currency_skips_nameless_and_handles_missing():
    payload = {"lines": [{"chaosEquivalent": 5}, {"currencyTypeName": "Chaos Orb"}]}
    rows = normalize_currency(payload, "test-league")
    assert len(rows) == 1
    assert rows[0].name == "Chaos Orb"
    assert rows[0].chaos_value is None


def test_normalize_items():
    payload = {"lines": [{"name": "Headhunter", "chaosValue": 9999, "divineValue": 40,
                          "listingCount": 3}]}
    rows = normalize_items(payload, "test-league", "unique")
    assert rows[0].name == "Headhunter"
    assert rows[0].divine_value == 40
    assert rows[0].item_type == "unique"


def test_normalize_handles_empty_payload():
    assert normalize_currency({}, "test-league") == []
    assert normalize_items({"lines": None}, "test-league", "gem") == []

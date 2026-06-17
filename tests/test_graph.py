from api.graph import build_graph

GUIDES = [
    {
        "name": "Ritual Omen",
        "items": [{"name": "Ritual Tablet"}],
        "sources": [{"url": "https://youtu.be/x", "title": "Ritual guide"}],
        "target_currency": "Divine Orb",
    },
    {
        "name": "Breach",
        "items": [{"name": "Ritual Tablet"}],  # shared item -> shared node
        "sources": [],
    },
]
SNAP = {"character_name": "Yuki", "gems": [{"name": "Fireball"}, "Spell Echo"]}
PRICES = [{"name": "Divine Orb", "divine_value": 1}, {"name": "Exalted Orb", "divine_value": 0.004}]


def test_build_graph_nodes_and_dedup():
    g = build_graph("Runes of Aldur", GUIDES, SNAP, PRICES)
    ids = {n["id"] for n in g["nodes"]}
    assert "league" in ids and "farm:Ritual Omen" in ids and "build" in ids
    # the shared item appears once (dedup)
    assert sum(1 for n in g["nodes"] if n["id"] == "item:ritual tablet") == 1
    types = {n["type"] for n in g["nodes"]}
    assert {"league", "farm", "item", "source", "build", "gem", "currency"} <= types


def test_build_graph_links_connect_farm_to_shared_item():
    g = build_graph("L", GUIDES, SNAP, PRICES)
    item_id = "item:ritual tablet"
    farms_linked = {lk["source"] for lk in g["links"] if lk["target"] == item_id}
    assert farms_linked == {"farm:Ritual Omen", "farm:Breach"}  # both link to the shared item


def test_build_graph_handles_no_snapshot():
    g = build_graph("L", [], None, [])
    assert g["nodes"] == [{"id": "league", "label": "L", "type": "league"}]
    assert g["links"] == []

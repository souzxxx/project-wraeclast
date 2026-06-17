from api.build_diff import compute_build_diff


def test_diff_without_meta_degrades_gracefully():
    mine = {"char_class": "Witch", "level": 90, "gems": [{"name": "Fireball"}]}
    out = compute_build_diff(mine, None)
    assert out["comparable"] is False
    assert out["my_gems"] == ["Fireball"]


def test_diff_with_meta_lists_add_and_cut():
    mine = {"char_class": "Witch", "level": 90,
            "gems": [{"name": "Fireball"}, {"name": "Spell Echo"}]}
    meta = {"char_class": "Witch", "gems": [{"name": "Fireball"}, {"name": "Comet"}]}
    out = compute_build_diff(mine, meta)
    assert out["comparable"] is True
    assert out["consider_adding"] == ["Comet"]
    assert out["consider_cutting"] == ["Spell Echo"]
    assert out["shared"] == ["Fireball"]


def test_diff_accepts_string_gems():
    mine = {"gems": ["Fireball", "Frostbolt"]}
    meta = {"gems": ["Fireball"]}
    out = compute_build_diff(mine, meta)
    assert out["consider_cutting"] == ["Frostbolt"]

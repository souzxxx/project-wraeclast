from collector.ninja_build_client import normalize_profile_character, pick_character

CHARS = [
    {"name": "OldGuy", "isCurrent": False, "className": "Witch", "level": 70, "skills": []},
    {
        "name": "YukinariSugawara",
        "isCurrent": True,
        "className": "Spirit Walker",
        "level": 90,
        "league": "Runes of Aldur",
        "skills": [
            {"name": "Twister", "icon": "i", "damage": [44571, 47]},
            {"name": "Wild Protector", "icon": "i2", "damage": [715, 78]},
            {"icon": "noname"},  # skipped
        ],
    },
]


def test_pick_character_prefers_current():
    assert pick_character(CHARS)["name"] == "YukinariSugawara"


def test_pick_character_honors_explicit_name():
    assert pick_character(CHARS, "OldGuy")["name"] == "OldGuy"


def test_normalize_profile_character_maps_fields_and_skills():
    snap = normalize_profile_character(pick_character(CHARS))
    assert snap.character_name == "YukinariSugawara"
    assert snap.char_class == "Spirit Walker"
    assert snap.level == 90
    names = {g["name"] for g in snap.gems}
    assert names == {"Twister", "Wild Protector"}  # nameless skill dropped
    assert snap.passive_tree["league"] == "Runes of Aldur"

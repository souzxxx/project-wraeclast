import httpx
import pytest
import respx

import collector.ninja_build_client as nbc
from collector.config import Settings
from collector.ninja_build_client import (
    CharacterNotOnLadder,
    _int,
    _main,
    _profile_endpoint,
    fetch_my_build,
    from_pob_code,
    normalize_profile_character,
    pick_character,
    run,
)
from collector.pob_parser import PoBParseError

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


def test_pick_character_falls_back_to_first_when_no_current():
    # explicit name that doesn't exist + nobody flagged isCurrent -> first character
    chars = [
        {"name": "A", "isCurrent": False},
        {"name": "B", "isCurrent": False},
    ]
    assert pick_character(chars, "DoesNotExist")["name"] == "A"


def test_normalize_profile_character_maps_fields_and_skills():
    snap = normalize_profile_character(pick_character(CHARS))
    assert snap.character_name == "YukinariSugawara"
    assert snap.char_class == "Spirit Walker"
    assert snap.level == 90
    names = {g["name"] for g in snap.gems}
    assert names == {"Twister", "Wild Protector"}  # nameless skill dropped
    assert snap.passive_tree["league"] == "Runes of Aldur"
    assert snap.gear == {}  # public profile never exposes gear


def test_normalize_profile_character_tolerates_missing_fields():
    # skills absent, level non-numeric -> defensive defaults, no crash
    snap = normalize_profile_character({"name": "Bare", "level": "??"})
    assert snap.character_name == "Bare"
    assert snap.char_class is None
    assert snap.level is None
    assert snap.gems == []
    assert snap.passive_tree == {"source": "ninja_profile", "league": None}


def test_int_parses_and_defaults_to_none():
    assert _int("42") == 42
    assert _int(7) == 7
    assert _int(None) is None
    assert _int("not-a-number") is None


def test_profile_endpoint_builds_versioned_path():
    settings = Settings(ninja_account="souzxxx")
    assert _profile_endpoint(settings) == "/poe2/api/profile/characters/souzxxx/0"
    assert _profile_endpoint(settings, version=3).endswith("/souzxxx/3")


async def test_fetch_my_build_requires_account():
    with pytest.raises(CharacterNotOnLadder):
        await fetch_my_build(Settings(ninja_account=""))


@respx.mock
async def test_fetch_my_build_happy_path():
    settings = Settings(ninja_account="souzxxx")
    route = respx.get(
        "https://poe.ninja/poe2/api/profile/characters/souzxxx/0"
    ).mock(return_value=httpx.Response(200, json=CHARS))
    snap = await fetch_my_build(settings)
    assert route.called
    assert snap.character_name == "YukinariSugawara"
    assert snap.level == 90


@respx.mock
async def test_fetch_my_build_empty_list_raises():
    settings = Settings(ninja_account="souzxxx")
    respx.get("https://poe.ninja/poe2/api/profile/characters/souzxxx/0").mock(
        return_value=httpx.Response(200, json=[])
    )
    with pytest.raises(CharacterNotOnLadder):
        await fetch_my_build(settings)


@respx.mock
async def test_fetch_my_build_non_list_raises():
    settings = Settings(ninja_account="souzxxx")
    respx.get("https://poe.ninja/poe2/api/profile/characters/souzxxx/0").mock(
        return_value=httpx.Response(200, json={"error": "private"})
    )
    with pytest.raises(CharacterNotOnLadder):
        await fetch_my_build(settings)


@respx.mock
async def test_fetch_my_build_http_error_becomes_not_on_ladder():
    settings = Settings(ninja_account="souzxxx")
    respx.get("https://poe.ninja/poe2/api/profile/characters/souzxxx/0").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(CharacterNotOnLadder):
        await fetch_my_build(settings)


def test_from_pob_code_rejects_garbage():
    # delegates to the PoB parser; garbage in -> PoBParseError out
    with pytest.raises(PoBParseError):
        from_pob_code("not-a-real-pob-code")


async def test_run_writes_snapshot_from_ninja(monkeypatch):
    snap = normalize_profile_character(pick_character(CHARS))
    written: list = []

    async def fake_fetch(settings):
        return snap

    monkeypatch.setattr(nbc, "fetch_my_build", fake_fetch)
    monkeypatch.setattr("db.repo.insert_my_snapshot", written.append)
    assert await run() is True
    assert written == [snap]


async def test_run_returns_false_when_off_ladder_without_pob(monkeypatch):
    async def fake_fetch(settings):
        raise CharacterNotOnLadder("below ladder minimum")

    monkeypatch.setattr(nbc, "fetch_my_build", fake_fetch)
    # no DB write should happen on this path
    monkeypatch.setattr(
        "db.repo.insert_my_snapshot",
        lambda *_: pytest.fail("must not write when no snapshot"),
    )
    assert await run(pob_code=None) is False


async def test_run_falls_back_to_pob_code(monkeypatch):
    sentinel = normalize_profile_character({"name": "FromPoB", "level": 5})
    written: list = []

    async def fake_fetch(settings):
        raise CharacterNotOnLadder("off ladder")

    monkeypatch.setattr(nbc, "fetch_my_build", fake_fetch)
    monkeypatch.setattr(nbc, "from_pob_code", lambda code: sentinel)
    monkeypatch.setattr("db.repo.insert_my_snapshot", written.append)
    assert await run(pob_code="some-pob-code") is True
    assert written == [sentinel]


def test_main_unknown_command_returns_2():
    assert _main(["prog", "bogus"]) == 2

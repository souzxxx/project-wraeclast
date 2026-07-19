"""Offline tests for meta-build aggregation (pure) and the network/dispatch surface
(fetch/run/explore/_main, mocked with respx + monkeypatch — no DB, no live network)."""

import httpx
import pytest
import respx

import collector.ninja_meta_client as nmc
from api.build_diff import compute_build_diff
from collector.config import Settings
from collector.ninja_meta_client import (
    _char_class,
    _char_gems,
    _main,
    aggregate_meta_builds,
    explore,
    extract_characters,
    fetch_popular_builds,
    run,
)

BUILDS_URL = "https://poe.ninja/poe2/api/builds/overview"


def _char(cls, *gems):
    return {"className": cls, "skills": [{"name": g} for g in gems]}


def test_extract_characters_from_bare_list():
    payload = [{"className": "Witch"}, "junk", {"className": "Monk"}]
    assert extract_characters(payload) == [{"className": "Witch"}, {"className": "Monk"}]


def test_extract_characters_from_wrapped_dict():
    payload = {"characters": [{"className": "Witch"}], "meta": "ignored"}
    assert extract_characters(payload) == [{"className": "Witch"}]


def test_extract_characters_tolerates_garbage():
    assert extract_characters(None) == []
    assert extract_characters({"nope": 1}) == []


def test_char_class_falls_back_across_keys():
    assert _char_class({"class": "Mercenary"}) == "Mercenary"
    assert _char_class({"foo": "bar"}) is None


def test_char_gems_prefers_skills_then_falls_back_and_dedupes_shape():
    assert _char_gems({"skills": [{"name": "Comet"}, "Frostbolt", {"icon": "x"}]}) == [
        "Comet",
        "Frostbolt",
    ]
    assert _char_gems({"allSkills": ["Spark"]}) == ["Spark"]
    assert _char_gems({"nope": []}) == []


def test_aggregate_ranks_by_usage_and_filters_min_usage():
    chars = [
        _char("Witch", "Comet", "Frostbolt"),
        _char("Witch", "Comet", "Spark"),
        _char("Witch", "Comet", "Frostbolt"),
        _char("Witch", "Comet"),
    ]
    [build] = aggregate_meta_builds(chars, "L", min_usage=0.5, min_sample=3)
    assert build.char_class == "Witch"
    assert build.sample_size == 4
    names = [g["name"] for g in build.gems]
    # Comet 4/4=100%, Frostbolt 2/4=50% kept; Spark 1/4=25% dropped (< min_usage)
    assert names == ["Comet", "Frostbolt"]
    assert build.gems[0] == {"name": "Comet", "usage_pct": 100.0}
    assert build.gems[1]["usage_pct"] == 50.0


def test_aggregate_counts_each_gem_once_per_character():
    # a character listing the same skill twice must not inflate usage past 100%.
    chars = [_char("Monk", "Tempest", "Tempest"), _char("Monk", "Tempest"), _char("Monk", "Ice")]
    [build] = aggregate_meta_builds(chars, "L", min_usage=0.1, min_sample=3)
    tempest = next(g for g in build.gems if g["name"] == "Tempest")
    assert tempest["usage_pct"] == 66.7  # 2 of 3 chars, not 3


def test_aggregate_skips_thin_classes_and_groups_by_class():
    chars = [
        _char("Witch", "Comet"),
        _char("Witch", "Comet"),
        _char("Witch", "Comet"),
        _char("Monk", "Tempest"),  # only one Monk -> below min_sample, skipped
    ]
    builds = aggregate_meta_builds(chars, "L", min_sample=3)
    assert [b.char_class for b in builds] == ["Witch"]


def test_aggregate_caps_max_gems_deterministically():
    chars = [_char("Witch", *[f"G{i}" for i in range(10)]) for _ in range(3)]
    [build] = aggregate_meta_builds(chars, "L", max_gems=4, min_sample=3)
    # all 10 gems tie at 100%; tie-break by name keeps it deterministic
    assert [g["name"] for g in build.gems] == ["G0", "G1", "G2", "G3"]


def test_aggregate_attaches_source_when_given():
    src = {"url": "https://poe.ninja/poe2/builds", "title": "poe.ninja builds"}
    [build] = aggregate_meta_builds(
        [_char("Witch", "Comet")] * 3, "L", min_sample=3, source=src
    )
    assert build.sources == [src]


def test_aggregate_output_feeds_build_diff():
    # the whole point: an aggregated meta build is consumable by compute_build_diff.
    chars = [_char("Witch", "Comet", "Spell Echo")] * 3
    [build] = aggregate_meta_builds(chars, "L", min_sample=3)
    mine = {"char_class": "Witch", "gems": [{"name": "Comet"}, {"name": "Fireball"}]}
    diff = compute_build_diff(mine, build.model_dump())
    assert diff["comparable"] is True
    assert diff["consider_adding"] == ["Spell Echo"]
    assert diff["consider_cutting"] == ["Fireball"]
    assert diff["shared"] == ["Comet"]


def test_aggregate_drops_class_with_no_qualifying_gems():
    # 3 chars, every gem unique -> each at 33%; min_usage=0.5 filters them all out, so the
    # class yields no gems and is dropped entirely (no empty-gem MetaBuild emitted).
    chars = [_char("Witch", "A"), _char("Witch", "B"), _char("Witch", "C")]
    assert aggregate_meta_builds(chars, "L", min_usage=0.5, min_sample=3) == []


@respx.mock
async def test_fetch_popular_builds_aggregates_from_endpoint():
    payload = {"characters": [_char("Witch", "Comet", "Frostbolt") for _ in range(3)]}
    route = respx.get(BUILDS_URL).mock(return_value=httpx.Response(200, json=payload))
    builds = await fetch_popular_builds(Settings())
    assert route.called
    [build] = builds
    assert build.char_class == "Witch"
    assert build.league == "Runes of Aldur"  # config default, not hardcoded in the client
    assert [g["name"] for g in build.gems] == ["Comet", "Frostbolt"]
    # the poe.ninja source is attached so the build-diff can cite where the meta came from
    assert build.sources == [{"url": "https://poe.ninja/poe2/builds", "title": "poe.ninja builds"}]


def test_ninja_builds_path_list_dedups_strips_and_orders():
    s = Settings(ninja_builds_path="/a", ninja_builds_alt_paths="/b, /a ,/c,")
    # primary first, then alts; whitespace stripped, blanks dropped, /a deduped to one entry.
    assert s.ninja_builds_path_list == ["/a", "/b", "/c"]


@respx.mock
async def test_fetch_popular_builds_falls_back_to_next_candidate():
    # the primary route 404s (the live prod symptom) — the fetch must probe the next candidate
    # instead of failing, and aggregate from whichever one actually returns characters.
    s = Settings(ninja_builds_path="/poe2/api/builds/overview", ninja_builds_alt_paths="/alt")
    payload = {"characters": [_char("Witch", "Comet", "Frostbolt") for _ in range(3)]}
    respx.get("https://poe.ninja/poe2/api/builds/overview").mock(
        return_value=httpx.Response(404)
    )
    alt = respx.get("https://poe.ninja/alt").mock(return_value=httpx.Response(200, json=payload))
    builds = await fetch_popular_builds(s)
    assert alt.called
    [build] = builds
    assert build.char_class == "Witch"
    assert [g["name"] for g in build.gems] == ["Comet", "Frostbolt"]


@respx.mock
async def test_fetch_popular_builds_skips_empty_payload_and_uses_next():
    # a candidate that returns 200 but no characters is not a valid meta source — move on.
    s = Settings(ninja_builds_path="/first", ninja_builds_alt_paths="/second")
    respx.get("https://poe.ninja/first").mock(
        return_value=httpx.Response(200, json={"characters": []})
    )
    payload = {"characters": [_char("Monk", "Tempest") for _ in range(3)]}
    respx.get("https://poe.ninja/second").mock(return_value=httpx.Response(200, json=payload))
    [build] = await fetch_popular_builds(s)
    assert build.char_class == "Monk"


@respx.mock
async def test_fetch_popular_builds_raises_when_all_candidates_fail():
    # every candidate dead -> raise loudly (run_daily surfaces it), never a silent empty meta.
    s = Settings(ninja_builds_path="/first", ninja_builds_alt_paths="/second")
    respx.get("https://poe.ninja/first").mock(return_value=httpx.Response(404))
    respx.get("https://poe.ninja/second").mock(return_value=httpx.Response(500))
    with pytest.raises(RuntimeError) as exc:
        await fetch_popular_builds(s)
    msg = str(exc.value)
    assert "/first" in msg and "/second" in msg  # both tried paths named for diagnosis


@respx.mock
async def test_explore_probes_candidates_and_reports_each(monkeypatch, capsys):
    s = Settings(ninja_builds_path="/first", ninja_builds_alt_paths="/second")
    monkeypatch.setattr(nmc, "get_settings", lambda: s)
    respx.get("https://poe.ninja/first").mock(return_value=httpx.Response(404))
    payload = {"characters": [_char("Witch", "Comet")]}
    respx.get("https://poe.ninja/second").mock(return_value=httpx.Response(200, json=payload))
    await explore()
    out = capsys.readouterr().out
    assert "/first: ERROR" in out  # the dead candidate is reported, not fatal
    assert "/second: characters found: 1" in out  # the working candidate + its count
    assert "Comet" in out  # sample dumped from the first hit


@respx.mock
async def test_explore_reports_when_no_candidate_returns_characters(monkeypatch, capsys):
    s = Settings(ninja_builds_path="/only", ninja_builds_alt_paths="")
    monkeypatch.setattr(nmc, "get_settings", lambda: s)
    respx.get("https://poe.ninja/only").mock(
        return_value=httpx.Response(200, json={"characters": []})
    )
    await explore()
    out = capsys.readouterr().out
    assert "/only: characters found: 0" in out
    assert "no candidate builds endpoint returned characters" in out


@respx.mock
async def test_fetch_popular_builds_truncates_to_max_chars():
    # 5 characters on the wire, but ninja_meta_max_chars caps the sample at 3 before aggregation.
    payload = {"characters": [_char("Witch", "Comet") for _ in range(5)]}
    respx.get(BUILDS_URL).mock(return_value=httpx.Response(200, json=payload))
    [build] = await fetch_popular_builds(Settings(ninja_meta_max_chars=3))
    assert build.sample_size == 3


async def test_run_writes_meta_builds(monkeypatch, capsys):
    builds = aggregate_meta_builds([_char("Witch", "Comet")] * 3, "Runes of Aldur", min_sample=3)

    async def fake_fetch(settings):
        return builds

    written: list = []
    monkeypatch.setattr(nmc, "fetch_popular_builds", fake_fetch)
    monkeypatch.setattr(
        "db.repo.replace_meta_builds",
        lambda league, b: written.append((league, b)) or len(b),
    )
    assert await run() == 1
    assert written == [("Runes of Aldur", builds)]
    assert "meta_build: wrote 1" in capsys.readouterr().out


@respx.mock
async def test_explore_dumps_character_count_and_sample(capsys):
    payload = {"characters": [_char("Witch", "Comet"), _char("Monk", "Tempest")]}
    respx.get(BUILDS_URL).mock(return_value=httpx.Response(200, json=payload))
    await explore()
    out = capsys.readouterr().out
    assert "characters found: 2" in out
    assert "Comet" in out  # first chars sampled into the JSON dump


def test_main_dispatches_run(monkeypatch):
    called: list = []
    monkeypatch.setattr(nmc.asyncio, "run", lambda coro: called.append(coro) or coro.close())
    assert _main(["prog", "run"]) == 0
    assert _main(["prog"]) == 0  # default command is run
    assert len(called) == 2


def test_main_dispatches_explore(monkeypatch):
    monkeypatch.setattr(nmc.asyncio, "run", lambda coro: coro.close())
    assert _main(["prog", "explore"]) == 0


def test_main_unknown_command_returns_2():
    assert _main(["prog", "bogus"]) == 2

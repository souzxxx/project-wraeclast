"""Offline tests for meta-build aggregation (pure), the protobuf wire decoding (pure), and the
network/dispatch surface (fetch/run/explore/_main, mocked with respx + monkeypatch — no DB, no
live network). Wire payloads are synthesized with the tiny encoder below, mirroring the shapes
confirmed against the live deploy on 2026-07-06."""

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
    build_characters,
    explore,
    fetch_popular_builds,
    parse_dictionary,
    parse_search,
    resolve_snapshot,
    run,
)

INDEX_URL = "https://poe.ninja/poe2/api/data/index-state"
SEARCH_URL = "https://poe.ninja/poe2/api/builds/2123-test/search"
DICT_URL = "https://poe.ninja/poe2/api/builds/dictionary/{}"

INDEX_STATE = {
    "snapshotVersions": [
        {"url": "other", "name": "Other League", "version": "1-x", "snapshotName": "other"},
        {
            "url": "runesofaldur",
            "name": "Runes of Aldur",
            "version": "2123-test",
            "snapshotName": "runes-of-aldur",
        },
    ]
}


# ── minimal protobuf encoder (test-side mirror of the client's wire decoder) ──


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _vi(field: int, n: int) -> bytes:
    return _varint(field << 3 | 0) + _varint(n)


def _ld(field: int, payload: bytes) -> bytes:
    return _varint(field << 3 | 2) + _varint(len(payload)) + payload


def _dict_payload(name: str, values: list[str]) -> bytes:
    return _ld(1, name.encode()) + b"".join(_ld(2, v.encode()) for v in values)


def _cell_num(n: int) -> bytes:
    return _vi(2, n) if n else b""  # proto3: default 0 is omitted on the wire


def _cell_nums(ns: list[int]) -> bytes:
    return _ld(3, b"".join(_varint(n) for n in ns))


def _column(column_id: str, cells: list[bytes]) -> bytes:
    return _ld(1, column_id.encode()) + b"".join(_ld(2, c) for c in cells)


def _search_payload(columns: list[bytes], refs: dict[str, str]) -> bytes:
    result = b"".join(_ld(5, c) for c in columns)
    result += b"".join(_ld(6, _ld(1, n.encode()) + _ld(2, h.encode())) for n, h in refs.items())
    return _ld(1, result)


def _search_wire(class_indices: list[int], skills_indices: list[list[int]]) -> bytes:
    return _search_payload(
        [
            _column("class", [_cell_num(i) for i in class_indices]),
            _column("skills", [_cell_nums(g) for g in skills_indices]),
        ],
        {"class": "cafe01", "gem": "beef02"},
    )


def _mock_ladder(class_names, gem_names, class_indices, skills_indices):
    respx.get(INDEX_URL).mock(return_value=httpx.Response(200, json=INDEX_STATE))
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, content=_search_wire(class_indices, skills_indices))
    )
    respx.get(DICT_URL.format("cafe01")).mock(
        return_value=httpx.Response(200, content=_dict_payload("class", class_names))
    )
    respx.get(DICT_URL.format("beef02")).mock(
        return_value=httpx.Response(200, content=_dict_payload("gem", gem_names))
    )


def _char(cls, *gems):
    return {"className": cls, "skills": [{"name": g} for g in gems]}


# ── wire decoding (pure) ──


def test_parse_dictionary_maps_position_to_name():
    buf = _dict_payload("class", ["Martial Artist", "Titan"])
    assert parse_dictionary(buf) == ["Martial Artist", "Titan"]


def test_parse_search_decodes_columns_and_dictionary_refs():
    columns, hashes = parse_search(_search_wire([0, 1], [[0, 2], []]))
    assert hashes == {"class": "cafe01", "gem": "beef02"}
    # proto3 default: the empty first cell decodes to index 0
    assert [c["num"] for c in columns["class"]] == [0, 1]
    assert [c["nums"] for c in columns["skills"]] == [[0, 2], []]


def test_parse_search_tolerates_unknown_fields_and_junk():
    # unknown result fields and a junk column (no id) are skipped, not fatal
    result = _vi(1, 999) + _ld(5, _ld(2, _cell_num(1))) + _ld(4, b"\x08\x01")
    columns, hashes = parse_search(_ld(1, result))
    assert columns == {} and hashes == {}


def test_build_characters_joins_dictionaries_and_drops_bad_indices():
    columns, _ = parse_search(_search_wire([0, 7, 1], [[0, 9], [0], [1]]))
    chars = build_characters(columns, ["Witch", "Monk"], ["Comet", "Frostbolt"])
    # class 7 is out of range -> row dropped; gem 9 out of range -> gem dropped
    assert chars == [_char("Witch", "Comet"), _char("Monk", "Frostbolt")]


def test_resolve_snapshot_matches_league_case_insensitively():
    assert resolve_snapshot(INDEX_STATE, "runes of aldur") == {
        "version": "2123-test",
        "snapshotName": "runes-of-aldur",
    }
    assert resolve_snapshot(INDEX_STATE, "Unknown League") is None
    assert resolve_snapshot(None, "Runes of Aldur") is None


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
async def test_fetch_popular_builds_aggregates_from_wire():
    # 3 Witch characters, all running Comet + Frostbolt (class 0, gems 0/1)
    _mock_ladder(["Witch"], ["Comet", "Frostbolt"], [0, 0, 0], [[0, 1], [0, 1], [0, 1]])
    builds = await fetch_popular_builds(Settings())
    [build] = builds
    assert build.char_class == "Witch"
    assert build.league == "Runes of Aldur"  # config default, not hardcoded in the client
    assert [g["name"] for g in build.gems] == ["Comet", "Frostbolt"]
    # the poe.ninja source is attached so the build-diff can cite where the meta came from
    assert build.sources == [{"url": "https://poe.ninja/poe2/builds", "title": "poe.ninja builds"}]


@respx.mock
async def test_fetch_popular_builds_truncates_to_max_chars():
    # 5 characters on the wire, but ninja_meta_max_chars caps the sample at 3 before aggregation.
    _mock_ladder(["Witch"], ["Comet"], [0] * 5, [[0]] * 5)
    [build] = await fetch_popular_builds(Settings(ninja_meta_max_chars=3))
    assert build.sample_size == 3


@respx.mock
async def test_fetch_popular_builds_fails_loud_when_league_missing():
    respx.get(INDEX_URL).mock(return_value=httpx.Response(200, json={"snapshotVersions": []}))
    with pytest.raises(RuntimeError, match="not found in poe.ninja index-state"):
        await fetch_popular_builds(Settings())


@respx.mock
async def test_fetch_popular_builds_fails_loud_when_dictionary_missing():
    respx.get(INDEX_URL).mock(return_value=httpx.Response(200, json=INDEX_STATE))
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, content=_search_payload([], {"class": "cafe01"}))
    )
    respx.get(DICT_URL.format("cafe01")).mock(
        return_value=httpx.Response(200, content=_dict_payload("class", ["Witch"]))
    )
    with pytest.raises(RuntimeError, match="no 'gem' dictionary"):
        await fetch_popular_builds(Settings())


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
    _mock_ladder(["Witch", "Monk"], ["Comet", "Tempest"], [0, 1], [[0], [1]])
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

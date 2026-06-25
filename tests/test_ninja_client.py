import httpx
import respx

import collector.ninja_client as nc
from collector.config import Settings
from collector.ninja_client import (
    _main,
    _num,
    explore,
    fetch_economy,
    normalize_exchange,
    run,
)

ECONOMY_URL = "https://poe.ninja/poe2/api/economy/exchange/0/overview"

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


def test_normalize_exchange_dedupes_names_within_a_run():
    payload = {
        "core": {"primary": "divine"},
        "lines": [{"id": "a", "primaryValue": 1}, {"id": "b", "primaryValue": 2}],
        "items": [{"id": "a", "name": "Dup"}, {"id": "b", "name": "Dup"}],  # same name twice
    }
    rows = normalize_exchange(payload, "L")
    assert [r.name for r in rows] == ["Dup"]  # one row per name


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


def test_num_parses_and_swallows_bad_values():
    assert _num("3.5") == 3.5
    assert _num(7) == 7.0
    assert _num(None) is None  # TypeError -> None
    assert _num("not-a-number") is None  # ValueError -> None


def test_normalize_exchange_skips_non_dict_lines():
    payload = {
        "core": {"primary": "divine"},
        "lines": ["junk", {"id": "a", "primaryValue": 1}],  # str line skipped, not fatal
        "items": [{"id": "a", "name": "Real"}],
    }
    rows = normalize_exchange(payload, "L")
    assert [r.name for r in rows] == ["Real"]


def test_normalize_exchange_unknown_base_records_under_divine():
    # core.primary is neither divine nor chaos -> value still recorded under divine (PoE2 base)
    payload = {
        "core": {"primary": "exalted"},
        "lines": [{"id": "a", "primaryValue": 9}],
        "items": [{"id": "a", "name": "Odd"}],
    }
    rows = normalize_exchange(payload, "L")
    assert rows[0].divine_value == 9
    assert rows[0].chaos_value is None


def test_normalize_exchange_falls_back_to_positional_item():
    # line has no id match -> by_id miss -> uses items[idx] at the same position
    payload = {
        "core": {"primary": "divine"},
        "lines": [{"primaryValue": 2}],  # no id
        "items": [{"name": "Positional"}],
    }
    rows = normalize_exchange(payload, "L")
    assert [r.name for r in rows] == ["Positional"]


@respx.mock
async def test_fetch_economy_collects_and_tags_every_category():
    settings = Settings(ninja_economy_types="Currency:currency,Essences:essence")
    route = respx.get(ECONOMY_URL).mock(return_value=httpx.Response(200, json=SAMPLE))
    rows = await fetch_economy(settings)
    assert route.call_count == 2  # one GET per configured category
    item_types = {r.item_type for r in rows}
    assert item_types == {"currency", "essence"}  # each category tagged distinctly


@respx.mock
async def test_fetch_economy_swallows_one_bad_category(monkeypatch):
    settings = Settings(ninja_economy_types="Currency:currency,Essences:essence")
    # Currency 500s; the run keeps going and still returns the essence rows.
    respx.get(ECONOMY_URL, params={"type": "Currency"}).mock(
        return_value=httpx.Response(500)
    )
    respx.get(ECONOMY_URL, params={"type": "Essences"}).mock(
        return_value=httpx.Response(200, json=SAMPLE)
    )
    rows = await fetch_economy(settings)
    assert rows and {r.item_type for r in rows} == {"essence"}


async def test_run_writes_snapshots(monkeypatch):
    rows = normalize_exchange(SAMPLE, "Runes of Aldur")

    async def fake_fetch():
        return rows

    written: list = []
    monkeypatch.setattr(nc, "fetch_economy", fake_fetch)
    monkeypatch.setattr(
        "db.repo.insert_price_snapshots", lambda r: written.append(r) or len(r)
    )
    assert await run() == len(rows)
    assert written == [rows]


@respx.mock
async def test_explore_dumps_sampled_json(capsys):
    respx.get(ECONOMY_URL).mock(return_value=httpx.Response(200, json=SAMPLE))
    await explore()
    out = capsys.readouterr().out
    assert "Orb of Alchemy" in out  # lines/items sampled to <=2, names preserved


@respx.mock
async def test_explore_handles_non_dict_payload(capsys):
    respx.get(ECONOMY_URL).mock(return_value=httpx.Response(200, json=["a", "b"]))
    await explore()
    assert "a" in capsys.readouterr().out


def test_main_dispatches_run(monkeypatch):
    called: list = []
    monkeypatch.setattr(nc.asyncio, "run", lambda coro: called.append(coro) or coro.close())
    assert _main(["prog", "run"]) == 0
    assert _main(["prog"]) == 0  # default command is run
    assert len(called) == 2


def test_main_dispatches_explore(monkeypatch):
    monkeypatch.setattr(nc.asyncio, "run", lambda coro: coro.close())
    assert _main(["prog", "explore"]) == 0


def test_main_unknown_command_returns_2():
    assert _main(["prog", "bogus"]) == 2

"""Offline tests for the curated craft-method seed (pure data — no DB/network)."""

import pytest
from pydantic import ValidationError

from collector.seed_craft_methods import seed_methods
from db.models import CraftMethod

_LEAGUE = "Test League"
_METHODS = seed_methods(_LEAGUE)


def test_methods_present_and_carry_league():
    assert len(_METHODS) >= 5
    assert all(m.league == _LEAGUE for m in _METHODS)


def test_each_method_is_well_formed():
    for m in _METHODS:
        assert m.name and m.item_base and m.output
        assert m.target_mods, f"{m.name} has no target mods"
        assert m.steps, f"{m.name} has no steps"
        assert m.archetype, f"{m.name} has no archetype"
        # success_prob is the one curated chance — present and a real probability
        assert m.success_prob is not None and 0 < m.success_prob <= 1


def test_inputs_are_priceable_currency_quantities():
    # inputs drive the EV engine: every key is a non-empty currency name, every qty positive.
    for m in _METHODS:
        assert m.inputs, f"{m.name} has no currency inputs"
        for currency, qty in m.inputs.items():
            assert isinstance(currency, str) and currency.strip()
            assert qty > 0


def test_sources_are_attributed():
    for m in _METHODS:
        assert m.sources, f"{m.name} has no source"
        for s in m.sources:
            assert s.get("url", "").startswith("http")
            assert s.get("title")


def test_method_names_are_unique():
    names = [m.name for m in _METHODS]
    assert len(names) == len(set(names))


def test_success_prob_must_be_a_probability():
    base = dict(league=_LEAGUE, name="x", item_base="b")
    with pytest.raises(ValidationError):
        CraftMethod(**base, success_prob=1.5)
    with pytest.raises(ValidationError):
        CraftMethod(**base, success_prob=-0.1)
    # the bounds are inclusive of 1 and 0
    assert CraftMethod(**base, success_prob=1.0).success_prob == 1.0

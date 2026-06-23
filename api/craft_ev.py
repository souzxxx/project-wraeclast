"""Craft 3 — calculated EV (the craft differentiator).

Pure core: cross a craft method's `inputs` with live consumable prices to get the expected cost
(including retries, via `success_prob`) and ROI against the curated `output_value_div`, then rank.

Craft is NOT just currency — `inputs` may name essences, omens, abyssal/rune/catalyst consumables.
We price every input we can from poe.ninja (the `price_snapshot` currency feed) and surface the
rest in `missing_prices`, so the EV is honest about what it couldn't value. The PRICES are live;
the success chance and output value are the method's curated estimates (same spirit as a farm's
estimated profit/hour). No I/O here, so the math is unit-testable fully offline.
"""

from __future__ import annotations

from typing import Any

# fields copied straight from the method onto the EV result (for the API/site/chat to render)
_PASSTHROUGH = (
    "name", "item_base", "archetype", "mechanics", "target_mods", "steps", "output",
    "output_value_div", "success_prob", "sources", "notes",
)


def _f(value: Any) -> float | None:
    """Coerce a possibly-Decimal/None numeric to float (psycopg returns NUMERIC as Decimal)."""
    return float(value) if value is not None else None


def price_index(prices: list[dict[str, Any]]) -> dict[str, float]:
    """Map consumable name -> unit value in the feed's own denomination. PoE2's poe.ninja feed is
    DIVINE-denominated (it leaves `chaos_value` null and fills `divine_value`), so fall back to
    `divine_value`; PoE1-style chaos data still works. Within a single feed the unit is consistent,
    and `Divine Orb` resolves to that unit's value (1.0 for the divine feed)."""
    index: dict[str, float] = {}
    for p in prices:
        name = p.get("name")
        value = _f(p.get("chaos_value"))
        if value is None:
            value = _f(p.get("divine_value"))
        if name and value is not None:
            # first occurrence wins (prices are fetched Currency-first), so a name shared across
            # mechanic categories resolves to its canonical currency price, not the last category's
            index.setdefault(name, value)
    return index


def method_ev(
    method: dict[str, Any], index: dict[str, float], divine_unit: float | None
) -> dict[str, Any]:
    """Compute the EV of one method against a price index. Pure.

    We only publish derived money fields (cost/profit/ROI) when the method is fully `priced` —
    every input valued, a real cost, and a usable success chance. Otherwise the cost would be an
    UNDER-count (missing inputs sum to 0) and ROI would be inflated, so those fields are None and
    consumers fall back to `missing_prices`."""
    inputs = method.get("inputs") or {}
    missing = sorted(name for name in inputs if name not in index)
    base_cost = sum(float(qty) * index[name] for name, qty in inputs.items() if name in index)

    sp = _f(method.get("success_prob"))
    invalid_sp = sp is not None and sp <= 0  # 0% (or negative) = never succeeds, not 1 attempt
    expected_attempts = (1.0 / sp) if sp and sp > 0 else 1.0

    # trust the EV only when every input is valued, it costs something, and success is usable
    priced = bool(not missing and base_cost > 0 and not invalid_sp)

    def to_div(value: float) -> float | None:
        return value / divine_unit if divine_unit and divine_unit > 0 else None

    base_cost_div = expected_cost_div = profit_div = roi_pct = None
    if priced:
        base_cost_div = to_div(base_cost)
        expected_cost_div = to_div(base_cost * expected_attempts)
        output_value = _f(method.get("output_value_div"))
        if output_value is not None and expected_cost_div is not None:
            profit_div = output_value - expected_cost_div
            if expected_cost_div > 0:
                roi_pct = profit_div / expected_cost_div * 100

    result = {k: method.get(k) for k in _PASSTHROUGH}
    result.update(
        {
            "expected_attempts": round(expected_attempts, 2),
            "base_cost_div": round(base_cost_div, 2) if base_cost_div is not None else None,
            "expected_cost_div": round(expected_cost_div, 2)
            if expected_cost_div is not None
            else None,
            "profit_div": round(profit_div, 2) if profit_div is not None else None,
            "roi_pct": round(roi_pct) if roi_pct is not None else None,
            "roi_pct_exact": roi_pct,  # unrounded — for threshold/crossing comparisons
            "missing_prices": missing,
            "priced": priced,
        }
    )
    return result


def rank_methods(
    methods: list[dict[str, Any]], prices: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rank methods by ROI: fully-priced + highest ROI first, unpriceable ones last."""
    index = price_index(prices)
    divine_unit = index.get("Divine Orb")
    evs = [method_ev(m, index, divine_unit) for m in methods]
    return sorted(
        evs,
        key=lambda e: (
            e["priced"],
            e["roi_pct"] if e["roi_pct"] is not None else float("-inf"),
        ),
        reverse=True,
    )

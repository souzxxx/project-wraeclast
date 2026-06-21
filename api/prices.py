"""Currency prices for the crafting bench — a pure projection of the latest price rows.

The bench maps each currency orb to its poe.ninja `name` and sums the live chaos value as the
user applies orbs, so it only needs `{name, chaos_value, divine_value}` for currency items.
Kept pure (like `api.price_history.build_sparklines`) so it is unit-testable offline.
"""

from __future__ import annotations

from typing import Any


def currency_prices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only named currency rows, projected to the fields the bench needs."""
    return [
        {
            "name": r["name"],
            "chaos_value": r.get("chaos_value"),
            "divine_value": r.get("divine_value"),
        }
        for r in rows
        if r.get("item_type") == "currency" and r.get("name")
    ]

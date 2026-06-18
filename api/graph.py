"""Build the "brain" graph: a snapshot of everything we know, linked like an Obsidian vault.

Pure assembly (no I/O) so it's unit-testable. Nodes are deduped by id, so shared sources/items
across farms become shared nodes — that's what gives the linked, Obsidian-like structure.
"""

from __future__ import annotations

from typing import Any


def _add_node(nodes: dict[str, dict[str, Any]], node_id: str, label: str, ntype: str) -> str:
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, "label": label[:80] or node_id, "type": ntype}
    return node_id


def build_graph(
    league: str,
    guides: list[dict[str, Any]],
    my_snapshot: dict[str, Any] | None,
    prices: list[dict[str, Any]],
    knowledge: list[dict[str, Any]] | None = None,
    max_currencies: int = 8,
) -> dict[str, list[dict[str, Any]]]:
    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, str]] = []

    league_id = _add_node(nodes, "league", league, "league")

    for g in guides:
        name = g.get("name")
        if not name:
            continue
        farm_id = _add_node(nodes, f"farm:{name}", name, "farm")
        links.append({"source": league_id, "target": farm_id})
        for item in g.get("items") or []:
            iname = item.get("name") if isinstance(item, dict) else str(item)
            if iname:
                links.append({"source": farm_id, "target": _add_node(
                    nodes, f"item:{iname.lower()}", iname, "item")})
        for src in g.get("sources") or []:
            url = src.get("url") if isinstance(src, dict) else str(src)
            title = (src.get("title") if isinstance(src, dict) else "") or url
            if url:
                links.append({"source": farm_id, "target": _add_node(
                    nodes, f"src:{url}", title, "source")})
        target = g.get("target_currency")
        if target:
            links.append({"source": farm_id, "target": _add_node(
                nodes, f"cur:{target.lower()}", target, "currency")})

    if my_snapshot:
        build_id = _add_node(
            nodes, "build", my_snapshot.get("character_name") or "My build", "build"
        )
        links.append({"source": league_id, "target": build_id})
        for gem in my_snapshot.get("gems") or []:
            gname = gem.get("name") if isinstance(gem, dict) else str(gem)
            if gname:
                links.append({"source": build_id, "target": _add_node(
                    nodes, f"gem:{gname.lower()}", gname, "gem")})

    def _val(p: dict[str, Any]) -> float:
        return p.get("divine_value") or p.get("chaos_value") or 0

    for p in sorted(prices, key=_val, reverse=True)[:max_currencies]:
        name = p.get("name")
        if name:
            cur_id = _add_node(nodes, f"cur:{name.lower()}", name, "currency")
            links.append({"source": league_id, "target": cur_id})

    # All community knowledge (YouTube guides etc.) as source nodes hanging off the league.
    # Shared ids dedup with guide-cited sources: such a node keeps its farm link AND gains a
    # league link — that's the linked, Obsidian-like structure.
    for chunk in knowledge or []:
        url = chunk.get("source_url")
        if not url:
            continue
        title = chunk.get("title") or url
        links.append({"source": league_id, "target": _add_node(nodes, f"src:{url}", title, "source")})

    return {"nodes": list(nodes.values()), "links": links}

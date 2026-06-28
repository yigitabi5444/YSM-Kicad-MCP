"""FastMCP server: seven read-only tools for understanding a KiCad project.

Every tool returns a compact summary and obeys the output budgets in
budgets.py. Nothing here mutates the project.
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from . import budgets, kicad
from .model import Board, is_ground, load

mcp = FastMCP("kicad-context")

# Project the server was pointed at (CLI arg / env). Tools may override.
_DEFAULT_PROJECT = os.environ.get("KICAD_PROJECT") or os.environ.get(
    "KICAD_PROJECT_DIR"
)


def _board(project: str | None) -> Board:
    target = project or _DEFAULT_PROJECT or os.getcwd()
    return load(target)


# --------------------------------------------------------------------------
@mcp.tool()
def board_overview(project: str | None = None) -> dict:
    """Orientation call. What is this board: title, sheets/function blocks,
    key ICs, power rails, connectors, and part counts. Make this first."""
    b = _board(project)
    counts: dict[str, int] = {}
    for c in b.components.values():
        counts[c.kind] = counts.get(c.kind, 0) + 1

    # key ICs = U/IC parts ranked by pin count
    pins = b.pins_of
    ics = [c for c in b.components.values() if c.kind == "IC"]
    ics.sort(key=lambda c: len(pins.get(c.ref, [])), reverse=True)
    key_ics = [
        budgets.label(f"{c.ref}: {c.value} ({len(pins.get(c.ref, []))} pins)"
                      + (f" — {c.description}" if c.description else ""))
        for c in ics[:10]
    ]

    rails = [budgets.label(f"{n.name} ({len(n.nodes)} pins)")
             for n in sorted(b.power_nets, key=lambda n: -len(n.nodes))[:15]]

    conns = [budgets.label(f"{c.ref}: {c.value}")
             for c in b.components.values() if c.kind == "connector"]
    conns.sort()

    return {
        "title": b.pro.stem,
        "path": str(b.pro),
        "function_blocks": [budgets.label(f"{s} ({n} parts)")
                            for s, n in sorted(b.sheets.items())],
        "key_ics": key_ics,
        "power_rails": rails,
        "connectors": conns[:15],
        "regulators": b.regulators[:15],
        "part_counts": dict(sorted(counts.items(), key=lambda x: -x[1])),
        "total_components": len(b.components),
        "total_nets": len(b.nets),
        "pcb": b.pcb_summary,
        "hint": "Drill in with find / component / net / trace / power_tree / checks.",
    }


@mcp.tool()
def find(query: str, kind: str = "component", page: int = 1,
         project: str | None = None) -> dict:
    """Search the board. kind = component | net | sheet. Returns a paginated
    list of matching IDs + one-line labels to feed into other tools."""
    b = _board(project)
    q = query.lower()
    items = []
    if kind == "component":
        for c in b.components.values():
            hay = f"{c.ref} {c.value} {c.part} {c.description} {c.footprint}".lower()
            if q in hay:
                items.append({"id": c.ref,
                              "label": budgets.label(f"{c.ref}: {c.value}"
                                                     f" [{c.kind}]")})
        items.sort(key=lambda d: d["id"])
    elif kind == "net":
        for n in b.nets:
            if q in n.name.lower():
                items.append({"id": n.name,
                              "label": budgets.label(f"{n.name} "
                                                     f"({len(n.nodes)} pins)")})
        items.sort(key=lambda d: d["id"])
    elif kind == "sheet":
        for s, n in sorted(b.sheets.items()):
            if q in s.lower():
                items.append({"id": s, "label": budgets.label(f"{s} ({n} parts)")})
    else:
        return {"error": "kind must be one of: component, net, sheet"}
    return budgets.paginate(items, page)


@mcp.tool()
def component(ref: str, project: str | None = None) -> dict:
    """Describe one component: value, footprint, datasheet, fields, and its
    pin -> net map. Use net() on a pin's net to expand connectivity."""
    b = _board(project)
    c = b.components.get(ref)
    if not c:
        return {"error": f"no component {ref}",
                "hint": "use find(query, kind='component')"}
    pins = b.pins_of.get(ref, [])
    return {
        "ref": c.ref, "value": c.value, "kind": c.kind,
        "footprint": c.footprint, "datasheet": c.datasheet,
        "library": f"{c.lib}:{c.part}" if c.lib else c.part,
        "description": c.description, "sheet": c.sheet,
        "fields": {k: v for k, v in c.fields.items() if v},
        "pin_count": len(pins),
        "pins": [budgets.label(f"{p['pin']} ({p['pinfunction'] or p['pintype']})"
                               f" -> {p['net']}") for p in pins],
    }


@mcp.tool()
def net(name: str, page: int = 1, project: str | None = None) -> dict:
    """List the pins on a net, grouped by component. Paginates large nets."""
    b = _board(project)
    n = b.net_by_name.get(name)
    if not n:
        return {"error": f"no net {name!r}", "hint": "use find(query, kind='net')"}
    grouped: dict[str, list] = {}
    for nd in n.nodes:
        grouped.setdefault(nd["ref"], []).append(
            nd["pin"] + (f"/{nd['pinfunction']}" if nd["pinfunction"] else ""))
    rows = [{"id": ref, "label": budgets.label(f"{ref}: {', '.join(p)}")}
            for ref, p in sorted(grouped.items())]
    out = budgets.paginate(rows, page, page_size=budgets.NET_PINS_BEFORE_PAGE)
    out.update(net=n.name, total_pins=len(n.nodes), is_power=n.is_power)
    return out


@mcp.tool()
def trace(ref: str, pin: str, depth: int = budgets.TRACE_DEFAULT_DEPTH,
          project: str | None = None) -> dict:
    """Walk connectivity from a pin outward, bounded by depth (max 3). One hop
    = crossing a net or passing through a component. Large nets are reported
    but not fully expanded, to stay bounded."""
    b = _board(project)
    depth = max(1, min(int(depth), budgets.TRACE_MAX_DEPTH))
    pins = b.pins_of
    if ref not in pins:
        return {"error": f"no component {ref}"}
    if not any(p["pin"] == str(pin) for p in pins[ref]):
        return {"error": f"{ref} has no pin {pin!r}",
                "available_pins": [p["pin"] for p in pins[ref]][:40]}
    BIG = budgets.NET_PINS_BEFORE_PAGE
    start = (ref, str(pin))
    seen_pins = {start}
    seen_nets = set()
    frontier = [start]
    levels = []
    truncated = []
    for hop in range(depth):
        nxt = []
        reached = []
        for (r, pn) in frontier:
            # the net this pin sits on
            netname = next((p["net"] for p in pins.get(r, [])
                            if p["pin"] == pn), None)
            if not netname or netname in seen_nets:
                continue
            seen_nets.add(netname)
            netobj = b.net_by_name.get(netname)
            nodes = netobj.nodes if netobj else []
            if len(nodes) > BIG:
                truncated.append(f"{netname} ({len(nodes)} pins, not expanded)")
                continue
            for nd in nodes:
                key = (nd["ref"], nd["pin"])
                if key in seen_pins:
                    continue
                seen_pins.add(key)
                reached.append(budgets.label(
                    f"{nd['ref']}.{nd['pin']} on {netname}"))
                # cross the component: enqueue its other pins
                for p in pins.get(nd["ref"], []):
                    k2 = (nd["ref"], p["pin"])
                    if k2 not in seen_pins:
                        nxt.append(k2)
        if reached:
            levels.append({"hop": hop + 1, "pins": reached})
        frontier = nxt
        if not frontier:
            break
    return {"from": f"{ref}.{pin}", "depth": depth, "levels": levels,
            "large_nets_skipped": truncated,
            "total_pins_reached": sum(len(l["pins"]) for l in levels)}


@mcp.tool()
def power_tree(rail: str | None = None, project: str | None = None) -> dict:
    """Regulators and the rails they feed. Heuristic (library/value match).
    Pass a rail name to filter. Use net() on a rail for its full fanout."""
    b = _board(project)
    pins = b.pins_of
    out = []
    for r in b.regulators:
        c = b.components[r]
        ins, outs = set(), set()
        for p in pins.get(r, []):
            nm = p["net"]
            if is_ground(nm):
                continue  # grounds aren't a fed rail
            netobj = b.net_by_name.get(nm)
            if p["pintype"] == "power_in":
                ins.add(nm)
            elif p["pintype"] == "power_out":
                outs.add(nm)
            elif netobj and netobj.is_power:
                outs.add(nm)  # power net on a non-input pin -> likely output
        outs -= ins  # a rail can't be both
        out.append({
            "ref": r, "value": c.value,
            "description": budgets.label(c.description),
            "input_rails": sorted(ins),
            "output_rails": sorted(outs),
        })
    if rail:
        out = [r for r in out
               if rail in r["input_rails"] or rail in r["output_rails"]]
    return {
        "regulators": out,
        "power_rails": [budgets.label(f"{n.name} ({len(n.nodes)} pins)")
                        for n in sorted(b.power_nets, key=lambda n: -len(n.nodes))],
        "note": "Regulator detection is heuristic; verify against the schematic.",
    }


@mcp.tool()
def checks(type: str = "erc", severity: str | None = None, page: int = 1,
          project: str | None = None) -> dict:
    """Run ERC (schematic) or DRC (board) and return counts by severity, then
    a capped detail list. Filter by severity to expand a class."""
    b = _board(project)
    if type == "erc":
        data = kicad.run_erc(b.sch)
    elif type == "drc":
        if not b.pcb:
            return {"error": "no .kicad_pcb in project"}
        data = kicad.run_drc(b.pcb)
    else:
        return {"error": "type must be 'erc' or 'drc'"}

    violations = []
    # DRC shape: top-level groups. ERC shape: per-sheet violations.
    for grp in ("violations", "unconnected_items", "schematic_parity"):
        violations.extend(data.get(grp, []))
    for sheet in data.get("sheets", []):
        for v in sheet.get("violations", []):
            violations.append({**v, "sheet": sheet.get("path", "/")})
    counts: dict[str, int] = {}
    for v in violations:
        sev = v.get("severity", "unknown")
        counts[sev] = counts.get(sev, 0) + 1

    rows = violations if not severity else [
        v for v in violations if v.get("severity") == severity]
    detail = [{
        "severity": v.get("severity", ""),
        "type": v.get("type", ""),
        "label": budgets.label(v.get("description", "")),
    } for v in rows]
    out = budgets.paginate(detail, page, page_size=budgets.CHECKS_INLINE_ROWS)
    out.update(check=type, counts_by_severity=counts, total_violations=len(violations))
    return out


def main():
    """stdio entry point."""
    mcp.run()


if __name__ == "__main__":
    main()

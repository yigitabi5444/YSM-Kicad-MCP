# KiCad Context MCP

A read-only MCP server for understanding KiCad projects. Point it at a board and
an agent can answer "what is this" and "what's wrong with it" without loading the
whole design into context.

## Overview

The server reads a KiCad project and exposes it through seven tools. Every tool
returns a compact summary and lets the agent drill down by ID; lists are capped
and paginated, so context stays small even on large boards. Connectivity and
ERC/DRC come from `kicad-cli`; component metadata comes from the exported
netlist. Built for KiCad 10.

It only reads. There are no tools that edit, place, route, or export.

## How to install

Requires only KiCad 10+ (for `kicad-cli`). The plugin ships a self-contained
binary — no Python, uv, or network needed.

Installed as a plugin, which works in both Claude Code and Claude Desktop. Add
the marketplace, then install:

```
/plugin marketplace add yigitabi5444/YSM-Kicad-MCP
/plugin install kicad-context@ysm
```

Pass a project path to any tool to use it.

The shipped binary is macOS (Apple Silicon). On another platform, run
`bash build.sh` to rebuild `bin/kicad-context-mcp` for your OS.

## Exposed tools

| Tool | Returns |
|------|---------|
| `board_overview` | Title, sheets, key ICs, power rails, connectors, part counts. Start here. |
| `find` | Paginated components, nets, or sheets matching a query. |
| `component` | One part: value, footprint, datasheet, fields, pin → net map. |
| `net` | Pins on a net, grouped by component, paginated. |
| `trace` | Pins connected to a given pin, bounded by depth (max 3). |
| `power_tree` | Regulators and the rails they feed. |
| `checks` | ERC or DRC results: counts by severity, then a capped detail list. |

## Changelog

### 0.1.0
- Initial release. Seven read-only tools, KiCad 10.

## License

MIT, see [LICENSE](LICENSE). KiCad itself is GPLv3 and is a separate install the
server calls out to; it is not bundled here.

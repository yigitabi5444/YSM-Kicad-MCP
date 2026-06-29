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

Requires KiCad 10+ and [uv](https://docs.astral.sh/uv/).

**Claude Code:**

```bash
claude mcp add kicad-context -- \
  uvx --from git+https://github.com/yigitabi5444/YSM-Kicad-MCP kicad-context-mcp
```

**Claude Desktop:** download
[`kicad-context.mcpb`](https://github.com/yigitabi5444/YSM-Kicad-MCP/releases/latest/download/kicad-context.mcpb)
and open it (Settings → Extensions, then drag it in). On install it asks for the
path to `uvx` — run `which uvx` to get it (usually `/opt/homebrew/bin/uvx` on
macOS), since the desktop app does not inherit your shell `PATH`.

Pass a project path to any tool to use it.

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

# KiCad Context MCP

A **read-only** [MCP](https://modelcontextprotocol.io) server that helps an AI
agent *understand* a KiCad project — what the board is, what it does, and what
might be wrong with it — without dumping the whole design into the agent's
context.

It is a **comprehension layer, not a design tool.** There are no tools that
place, route, edit, or export anything. The server only reads.

> Built and tested against **KiCad 10**. Needs `kicad-cli` on the machine.

## Why another KiCad MCP?

Existing KiCad MCP servers tend to pour full netlists and per-track data into
the model, blowing the context budget. This one is built around one constraint:

**Progressive disclosure with hard output budgets.** Every tool returns a
compact summary by default and lets the agent drill down by ID. Every list is
capped and paginated. `board_overview` aims for ~500 tokens. You get *counts
first*, then detail only when asked.

## Tools

| Tool | What it answers | Drill-down |
|------|-----------------|-----------|
| `board_overview` | What is this board? Title, sheets/function blocks, key ICs, power rails, connectors, part counts. | the orientation call — start here |
| `find` | Where is X? Paginated matching components / nets / sheets. | feed IDs to `component` / `net` |
| `component` | What is U3? Value, footprint, datasheet, fields, pin→net map. | `net` on a pin's net |
| `net` | What's on this net? Pins grouped by component, paginated. | pagination for big nets |
| `trace` | What's connected to this pin within N hops? | raise `depth` (max 3) |
| `power_tree` | Which regulators feed which rails? | `net` on a rail |
| `checks` | ERC / DRC results, counts first then capped detail. | filter by `severity` |

### Output budgets

Defined in [`budgets.py`](src/kicad_context_mcp/budgets.py) so they're easy to
tune: default page 25 (max 100), net pins 40/page, trace depth 1 (max 3),
checks 20 detail rows inline, labels ≤120 chars. Every list returns
`{items, total, page, page_size, has_more}` so a truncated result is never
mistaken for a complete one.

## How it works

- **Connectivity, ERC, DRC** come from `kicad-cli` — we never reimplement
  KiCad's netlist resolution. The schematic is exported to a kicadxml netlist
  (components, fields, footprints, datasheets, sheet paths *and* full
  connectivity in one stdlib-parseable file).
- **PCB layer/stackup summary** comes from a small S-expression parse of
  `.kicad_pcb`.
- Results are cached per session and invalidated on file mtime change; netlist
  export (the slow path) is cached aggressively.

## Install

```bash
git clone https://github.com/yigitabi5444/YSM-Kicad-MCP.git
cd YSM-Kicad-MCP
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

You also need KiCad 10 installed (for `kicad-cli`):

```bash
# macOS
brew install --cask kicad
# Debian/Ubuntu
sudo add-apt-repository ppa:kicad/kicad-9.0-releases && sudo apt install kicad
```

The server finds `kicad-cli` via `$KICAD_CLI`, then `PATH`, then the macOS app
bundle (`/Applications/KiCad/KiCad.app/...`). Set `KICAD_CLI` if it lives
elsewhere.

## Use with Claude Code / Claude Desktop

Add to your MCP client config:

```json
{
  "mcpServers": {
    "kicad-context": {
      "command": "/abs/path/YSM-Kicad-MCP/.venv/bin/kicad-context-mcp",
      "env": { "KICAD_PROJECT": "/abs/path/to/your/project" }
    }
  }
}
```

`KICAD_PROJECT` points at a project directory or any project file. Every tool
also takes an optional `project` argument to override it per call.

## Read-only by design

There are no write tools. The server only ever reads the project files and runs
`kicad-cli` export/check subcommands. Point it at a project and it cannot change
it.

## Development

```bash
pip install -e . pytest
pytest
```

See [`tests/fixtures/README.md`](tests/fixtures/README.md) for the real-world
boards the test suite runs against.

## License

MIT (this server). KiCad itself is GPLv3 and is *not* bundled here — it's a
separate install the server shells out to.

# Test fixtures

The test suite runs against **any** KiCad project it finds under this directory
(`*.kicad_pro`, searched recursively) and skips entirely if none are present or
`kicad-cli` isn't installed. Real boards aren't committed here — they're large
and carry their own licenses — so populate this folder first.

## Option A — official KiCad demos (recommended)

KiCad ships a set of demo projects, including genuinely complex ones. Run:

```bash
./tests/fetch_fixtures.sh
```

This sparse-checks-out three demos from the official KiCad source mirror:

| Demo | Why it's here |
|------|---------------|
| `jetson-agx-thor-baseboard` | Large real-world Antmicro board: 1500+ parts, 15 hierarchical sheets, many power rails — the connectivity/budget stress test |
| `complex_hierarchy` | Exercises hierarchical sheet handling |
| `video` | Smaller board with a regulator chain for `power_tree` |

If you already have KiCad installed, you can instead just copy from its bundled
demos folder, e.g. on macOS:

```bash
cp -R "/Volumes/KiCad/demos/complex_hierarchy" tests/fixtures/   # from the installer DMG
# or from a system install:
cp -R /usr/share/kicad/demos/complex_hierarchy tests/fixtures/   # Linux
```

## Option B — your own project

Drop any `.kicad_pro` (with its `.kicad_sch`, and optionally `.kicad_pcb`)
anywhere under `tests/fixtures/` and the suite will pick it up.

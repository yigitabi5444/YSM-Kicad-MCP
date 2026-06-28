"""Thin subprocess wrapper around `kicad-cli`.

We never reimplement what kicad-cli does well: netlist resolution and ERC/DRC.
Generated artifacts are cached per (file, mtime) in a temp dir.
"""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class KicadError(RuntimeError):
    pass


def cli_path() -> str:
    """Locate kicad-cli: $KICAD_CLI, then PATH, then the macOS app bundle."""
    env = os.environ.get("KICAD_CLI")
    if env and Path(env).exists():
        return env
    found = shutil.which("kicad-cli")
    if found:
        return found
    rel = "KiCad.app/Contents/MacOS/kicad-cli"
    for base in ("/Applications/KiCad", str(Path.home() / "Applications")):
        cand = Path(base) / rel
        if cand.exists():
            return str(cand)
    raise KicadError(
        "kicad-cli not found. Install KiCad, or set KICAD_CLI to its path."
    )


def _run(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            [cli_path(), *args],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired as e:
        raise KicadError(f"kicad-cli timed out: {' '.join(args)}") from e
    if proc.returncode != 0:
        raise KicadError(
            f"kicad-cli {' '.join(args)} failed:\n{proc.stderr or proc.stdout}"
        )
    return proc.stdout


# artifacts go under a stable temp dir, keyed by source mtime
_ARTDIR = Path(tempfile.gettempdir()) / "kicad-context-mcp"


def _artifact(src: Path, suffix: str) -> Path:
    _ARTDIR.mkdir(exist_ok=True)
    stamp = int(src.stat().st_mtime)
    return _ARTDIR / f"{src.stem}.{stamp}{suffix}"


def export_netlist_xml(sch: Path) -> Path:
    """Export the schematic netlist as kicadxml; cached on mtime."""
    out = _artifact(sch, ".netlist.xml")
    if not out.exists():
        _run(["sch", "export", "netlist", "--format", "kicadxml",
              "-o", str(out), str(sch)])
    return out


def run_erc(sch: Path) -> dict:
    out = _artifact(sch, ".erc.json")
    if not out.exists():
        # erc exits non-zero when violations exist; tolerate that.
        try:
            _run(["sch", "erc", "--format", "json", "--exit-code-violations",
                  "-o", str(out), str(sch)])
        except KicadError:
            if not out.exists():
                raise
    return json.loads(out.read_text())


def run_drc(pcb: Path) -> dict:
    out = _artifact(pcb, ".drc.json")
    if not out.exists():
        try:
            _run(["pcb", "drc", "--format", "json", "--exit-code-violations",
                  "-o", str(out), str(pcb)])
        except KicadError:
            if not out.exists():
                raise
    return json.loads(out.read_text())

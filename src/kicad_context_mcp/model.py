"""Normalized, read-only board model built from kicad-cli output.

Spine of the data is the exported netlist XML (kicadxml): it already carries
components, fields, footprints, datasheets, sheet paths, pin types AND full
connectivity. The .kicad_pcb is parsed only for a layer/stackup summary.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from . import kicad, sexpr

# --- heuristics -----------------------------------------------------------
# Power rail name patterns (GND, VCC, +3V3, VDD, VBAT, AVDD, 1V8 ...)
POWER_NAME = re.compile(
    r"^(?:[+\-]?\d+(?:[V.]\d*)?V?|gnd|gnd\w*|a?gnd|v(?:cc|dd|ss|bat|in|out|ee|aa)\w*"
    r"|a?v(?:cc|dd)\w*|\+?\d+v\d*|vbus|vsys|pgnd)$",
    re.IGNORECASE,
)
POWER_PINTYPES = {"power_in", "power_out", "power"}
GROUND_NAME = re.compile(r"^(?:[apd]?gnd\w*|ground|vss\w*|pgnd)$", re.I)
REG_LIB = re.compile(r"regulator", re.I)
REG_DESC = re.compile(r"regulator|\bLDO\b|dc[\-/ ]?dc|buck|boost|switching", re.I)
# ref-designator prefix -> human category
PREFIX_KIND = {
    "U": "IC", "Q": "transistor", "D": "diode", "R": "resistor",
    "C": "capacitor", "L": "inductor", "Y": "crystal", "X": "crystal",
    "J": "connector", "P": "connector", "CN": "connector", "SW": "switch",
    "K": "relay", "T": "transformer", "F": "fuse", "FB": "ferrite",
    "LED": "LED", "TP": "testpoint", "JP": "jumper", "BT": "battery",
    "M": "mounting", "H": "mounting",
}


def ref_prefix(ref: str) -> str:
    m = re.match(r"^[A-Za-z]+", ref)
    return m.group(0).upper() if m else "?"


def ref_kind(ref: str) -> str:
    p = ref_prefix(ref)
    return PREFIX_KIND.get(p, PREFIX_KIND.get(p[:1], "other"))


def is_power_net(name: str, pintypes: set[str]) -> bool:
    if POWER_NAME.match(name.strip()):
        return True
    return bool(pintypes & POWER_PINTYPES)


def is_ground(name: str) -> bool:
    return bool(GROUND_NAME.match(name.strip()))


@dataclass
class Component:
    ref: str
    value: str = ""
    footprint: str = ""
    datasheet: str = ""
    lib: str = ""
    part: str = ""
    description: str = ""
    sheet: str = "/"
    fields: dict = field(default_factory=dict)

    @property
    def kind(self) -> str:
        return ref_kind(self.ref)


@dataclass
class Net:
    code: str
    name: str
    nodes: list  # list of dict: {ref, pin, pinfunction, pintype}

    @property
    def pintypes(self) -> set:
        return {n.get("pintype", "") for n in self.nodes}

    @property
    def is_power(self) -> bool:
        return is_power_net(self.name, self.pintypes)


@dataclass
class Board:
    pro: Path
    sch: Path
    pcb: Path | None
    components: dict  # ref -> Component
    nets: list        # list[Net]

    # --- derived indexes (built once) ------------------------------------
    @cached_property
    def net_by_name(self) -> dict:
        return {n.name: n for n in self.nets}

    @cached_property
    def pins_of(self) -> dict:
        """ref -> list of {pin, net, pinfunction, pintype}."""
        out: dict[str, list] = {}
        for net in self.nets:
            for nd in net.nodes:
                out.setdefault(nd["ref"], []).append(
                    {"pin": nd["pin"], "net": net.name,
                     "pinfunction": nd.get("pinfunction", ""),
                     "pintype": nd.get("pintype", "")}
                )
        for lst in out.values():
            lst.sort(key=lambda d: _natkey(d["pin"]))
        return out

    @cached_property
    def sheets(self) -> dict:
        """sheet path -> component count."""
        out: dict[str, int] = {}
        for c in self.components.values():
            out[c.sheet] = out.get(c.sheet, 0) + 1
        return out

    @cached_property
    def power_nets(self) -> list:
        return [n for n in self.nets if n.is_power]

    @cached_property
    def regulators(self) -> list:
        """Heuristic list of regulator refs (library/description match)."""
        regs = []
        for c in self.components.values():
            if REG_LIB.search(c.lib) or REG_DESC.search(c.description) \
               or REG_DESC.search(c.value):
                regs.append(c.ref)
        return sorted(regs, key=_natkey)

    # --- PCB summary (lazy, optional) ------------------------------------
    @cached_property
    def pcb_summary(self) -> dict:
        if not self.pcb or not self.pcb.exists():
            return {}
        try:
            doc = sexpr.parse(self.pcb.read_text())
        except Exception:
            return {}
        layers = sexpr.first(doc, "layers")
        layer_names = []
        if layers:
            for entry in layers[1:]:
                if isinstance(entry, list) and len(entry) >= 2:
                    layer_names.append(entry[1])
        copper = [n for n in layer_names if n.endswith(".Cu")]
        return {
            "layers_total": len(layer_names),
            "copper_layers": len(copper),
            "footprints": sum(1 for _ in sexpr.find_all(doc, "footprint")),
        }


def _natkey(s: str):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", str(s))]


# --- project resolution + parsing -----------------------------------------
def resolve_project(path: str | os.PathLike) -> tuple[Path, Path, Path | None]:
    """Return (pro, sch, pcb) for a project dir or any project file path."""
    p = Path(path).expanduser().resolve()
    if p.is_dir():
        pros = sorted(p.glob("*.kicad_pro"))
        if not pros:
            raise FileNotFoundError(f"no .kicad_pro in {p}")
        pro = pros[0]
    elif p.suffix == ".kicad_pro":
        pro = p
    elif p.suffix in (".kicad_sch", ".kicad_pcb"):
        pro = p.with_suffix(".kicad_pro")
    else:
        raise FileNotFoundError(f"not a KiCad project: {p}")
    sch = pro.with_suffix(".kicad_sch")
    pcb = pro.with_suffix(".kicad_pcb")
    if not sch.exists():
        raise FileNotFoundError(f"no schematic next to {pro.name}")
    return pro, sch, (pcb if pcb.exists() else None)


def _parse_netlist(xml_path: Path) -> tuple[dict, list]:
    root = ET.parse(xml_path).getroot()
    comps: dict[str, Component] = {}
    for comp in root.findall("./components/comp"):
        ref = comp.get("ref", "")
        fields = {f.get("name", ""): (f.text or "")
                  for f in comp.findall("./fields/field")}
        lib = part = desc = ""
        libsrc = comp.find("libsource")
        if libsrc is not None:
            lib = libsrc.get("lib", "")
            part = libsrc.get("part", "")
            desc = libsrc.get("description", "")
        sp = comp.find("sheetpath")
        sheet = sp.get("names", "/") if sp is not None else "/"
        comps[ref] = Component(
            ref=ref,
            value=(comp.findtext("value") or ""),
            footprint=(comp.findtext("footprint") or ""),
            datasheet=(comp.findtext("datasheet") or ""),
            lib=lib, part=part, description=desc, sheet=sheet, fields=fields,
        )
    nets: list[Net] = []
    for net in root.findall("./nets/net"):
        nodes = [
            {"ref": n.get("ref", ""), "pin": n.get("pin", ""),
             "pinfunction": n.get("pinfunction", ""),
             "pintype": n.get("pintype", "")}
            for n in net.findall("node")
        ]
        nets.append(Net(code=net.get("code", ""),
                        name=net.get("name", "") or f"(net {net.get('code')})",
                        nodes=nodes))
    return comps, nets


# --- mtime-keyed session cache --------------------------------------------
_CACHE: dict[str, tuple] = {}


def load(path: str | os.PathLike) -> Board:
    """Load (or return cached) Board for a project. Invalidates on mtime."""
    pro, sch, pcb = resolve_project(path)
    key = str(pro)
    stamp = (sch.stat().st_mtime, pcb.stat().st_mtime if pcb else 0)
    cached = _CACHE.get(key)
    if cached and cached[0] == stamp:
        return cached[1]
    xml_path = kicad.export_netlist_xml(sch)
    comps, nets = _parse_netlist(xml_path)
    board = Board(pro=pro, sch=sch, pcb=pcb, components=comps, nets=nets)
    _CACHE[key] = (stamp, board)
    return board

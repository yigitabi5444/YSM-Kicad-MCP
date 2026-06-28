"""Tool + budget tests, run against every project under tests/fixtures/.

Skips cleanly when kicad-cli or fixtures are absent (see fixtures/README.md).
"""

import os
from pathlib import Path

import pytest

os.environ.setdefault(
    "KICAD_CLI", os.path.expanduser("~/Applications/KiCad.app/Contents/MacOS/kicad-cli")
)

from kicad_context_mcp import budgets, kicad, server  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
PROJECTS = sorted(str(p) for p in FIX.rglob("*.kicad_pro"))

try:
    kicad.cli_path()
    HAVE_CLI = True
except Exception:
    HAVE_CLI = False

pytestmark = pytest.mark.skipif(
    not PROJECTS or not HAVE_CLI,
    reason="need kicad-cli + at least one project under tests/fixtures/",
)


@pytest.fixture(params=PROJECTS, ids=lambda p: Path(p).stem)
def proj(request):
    return request.param


# --- pure unit tests (no kicad needed) ------------------------------------
def test_paginate_caps_page_size():
    out = budgets.paginate(list(range(500)), page=1, page_size=99999)
    assert out["page_size"] == budgets.MAX_PAGE
    assert len(out["items"]) == budgets.MAX_PAGE
    assert out["has_more"] is True
    assert out["total"] == 500


def test_paginate_last_page():
    out = budgets.paginate(list(range(10)), page=1, page_size=25)
    assert out["has_more"] is False
    assert out["total"] == 10


def test_label_clamped():
    assert len(budgets.label("x" * 999)) <= budgets.LABEL_MAX


# --- tool tests (per fixture) ---------------------------------------------
def test_overview_within_budget(proj):
    import json

    ov = server.board_overview(proj)
    assert ov["total_components"] > 0
    # part_counts must account for every component
    assert sum(ov["part_counts"].values()) == ov["total_components"]
    # soft target is 500; hard ceiling well below a full netlist dump
    assert budgets.est_tokens(json.dumps(ov)) < 1500
    for lbl in ov["key_ics"]:
        assert len(lbl) <= budgets.LABEL_MAX


def test_find_paginates(proj):
    res = server.find("", kind="net", project=proj)  # "" matches all
    assert set(res) >= {"items", "total", "page", "page_size", "has_more"}
    assert len(res["items"]) <= res["page_size"]
    if res["total"] > res["page_size"]:
        assert res["has_more"] is True


def test_component_roundtrip(proj):
    first = server.find("U", kind="component", project=proj)["items"]
    if not first:
        pytest.skip("no U-prefixed parts")
    ref = first[0]["id"]
    c = server.component(ref, project=proj)
    assert c["ref"] == ref
    assert c["pin_count"] == len(c["pins"])
    for lbl in c["pins"]:
        assert len(lbl) <= budgets.LABEL_MAX


def test_net_connectivity_matches_model(proj):
    """net() pin count must match the parsed netlist (kicad-cli ground truth)."""
    from kicad_context_mcp import model

    b = model.load(proj)
    big = max(b.nets, key=lambda n: len(n.nodes))
    res = server.net(big.name, project=proj)
    assert res["total_pins"] == len(big.nodes)
    assert len(res["items"]) <= res["page_size"]


def test_trace_bounded_and_validates_pin(proj):
    from kicad_context_mcp import model

    b = model.load(proj)
    ref = next(iter(b.components))
    pins = b.pins_of.get(ref, [])
    if not pins:
        pytest.skip("first component has no pins")
    t = server.trace(ref, pins[0]["pin"], depth=3, project=proj)
    assert t["depth"] <= budgets.TRACE_MAX_DEPTH
    assert all(l["hop"] <= 3 for l in t["levels"])
    bad = server.trace(ref, "___nope___", project=proj)
    assert "error" in bad


def test_checks_counts_first(proj):
    erc = server.checks("erc", project=proj)
    assert "counts_by_severity" in erc
    assert len(erc["items"]) <= budgets.CHECKS_INLINE_ROWS


def test_server_is_read_only():
    import asyncio

    names = [t.name for t in asyncio.run(server.mcp.list_tools())]
    banned = ("write", "edit", "place", "route", "export", "delete", "set_")
    assert not any(b in n for n in names for b in banned)

#!/usr/bin/env python3
"""Named regressions for the on-chip oscillator driver identity.

Host-only.  Third hard-IP fixture, after `pll_check.py` and `spram_check.py`.

The gap: HFOSC and LFOSC reach `glb_netwk_*` with no source segment of their
own, exactly like a PLL global output.  Both oscillator-driven globals were
therefore driverless nets -- 832 and 830 segments of pure `lutff_global` sinks
-- and a second source routed onto one produced no conflict.

Two things here were measured rather than assumed:

  * which padin index belongs to which oscillator.  Placing HFOSC alone sets
    `padin_glb_netwk 4`; placing LFOSC alone sets 5.  The mapping is not taken
    from icebox's comment, which annotates a different device's table.
  * that a `padin_glb_netwk` extra bit means an on-chip source.  Driving a
    global from package pin 23 -- the very pad that shares padin index 4 -- sets
    no extra bit at all and puts the pad's own `io_0/D_IN_0` in the component.
    So pad-driven and hard-IP-driven globals are distinguishable, and the model
    annotates only the two indices it has evidence for.

`CLKHF_DIV` IS asserted below.  An earlier revision claimed the divider left no
trace in the ASC; that was wrong.  It is encoded in `dsp1_tile (0,16)` as two
IpConfig bits, `CBIT_3` low and `CBIT_4` high, and the earlier measurement
missed it only because the tile enumeration omitted `dsp_tiles`.
`work/osc_evidence.py` rebuilds all four divider values and pins the encoding.
"""

from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import exhaustive  # noqa: E402
from exhaustive import GlobalDriverGraph, tile_model  # noqa: E402
from iceutil import load_icebox, signed_tile_bits  # noqa: E402
from oracle import (  # noqa: E402
    conflicting_nets,
    oscillator_fabric_endpoints,
    driver_identity,
    oscillator_driver_state,
    pll_driver_state,
    spram_driver_state,
)
from pll_check import enabled_routes  # noqa: E402

ASC = Path(sys.argv[1] if len(sys.argv) > 1 else "build/osc.asc")
SELECTOR_ASC = ASC.with_name("osc_selector.asc")
FABRIC_SELECTOR_ASC = ASC.with_name("osc_fabric_selector.asc")
PROBE_TILE = (12, 31)
# The oscillator's other output.  The pre-set drives a span that reaches the
# HFOSC fabric segment's destination; the flip then puts the oscillator on it.
FABRIC_PRESET = (1, 27, "B11[51]", "lutff_5/out", "sp4_v_b_26")
FABRIC_FLIP = (0, 28, "B15[52]", "slf_op_7", "sp4_r_v_b_15")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def load(path: Path):
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(path))
    return icebox, ic


def set_bit(ic, x, y, name, value):
    row, column = name[1:].rstrip("]").split("[")
    row, column = int(row), int(column)
    tile = ic.tile(x, y)
    tile[row] = tile[row][:column] + value + tile[row][column + 1 :]


def main() -> int:
    icebox, ic = load(ASC)

    print("=== both oscillators are enabled (read from configuration) ===")
    extra = sorted(ic.lookup_extra_bit(bit) for bit in ic.extra_bits)
    print(f"  extra bits: {extra}")
    check("HFOSC's padin_glb_netwk 4 is set", ("padin_glb_netwk", "4") in extra)
    check("LFOSC's padin_glb_netwk 5 is set", ("padin_glb_netwk", "5") in extra)

    graph = GlobalDriverGraph(ic, icebox)
    sources = graph.oscillator_sources
    print(f"\n  oscillator source endpoints: {sources}")
    check(
        "HFOSC annotates its global network",
        sources.get((19, 31, "glb_netwk_4")) == ("hfosc", 19, 31),
    )
    check(
        "LFOSC annotates its global network",
        sources.get((6, 31, "glb_netwk_5")) == ("lfosc", 6, 31),
    )
    divider = {}
    for name, bit in (("CBIT_3", "B2[7]"), ("CBIT_4", "B5[7]")):
        row, column = bit[1:].rstrip("]").split("[")
        divider[name] = ic.dsp_tiles[1][(0, 16)][int(row)][int(column)]
    check(
        f"CLKHF_DIV reads back as 0b10 (CBIT_4={divider['CBIT_4']}, "
        f"CBIT_3={divider['CBIT_3']})",
        divider == {"CBIT_4": "1", "CBIT_3": "0"},
        "encoded in dsp1_tile (0,16); see work/osc_evidence.py",
    )
    check("model baseline has no multi-driver net", graph.base_multi_driver_nets == 0)
    check("oracle baseline has no conflicting net", conflicting_nets(ic, icebox) == 0)
    check(
        "glb_netwk_* is not itself a source",
        driver_identity(ic, icebox, (0, 1, "glb_netwk_4")) is None,
        "only the endpoint the oscillator actually feeds is annotated",
    )

    # --- generated selector baseline, never hand-edited ----------------------
    print("\n=== generating the oscillator test baseline ===")
    icebox_s, ic_s = load(ASC)
    before_routes = enabled_routes(ic_s, icebox_s)
    before_conflicts = conflicting_nets(ic_s, icebox_s)
    for name in ("B5[14]", "B5[15]"):
        set_bit(ic_s, *PROBE_TILE, name, "1")
    after_routes = enabled_routes(ic_s, icebox_s)
    after_conflicts = conflicting_nets(ic_s, icebox_s)
    check(
        "selector pre-set adds or removes no route",
        before_routes == after_routes,
        f"+{len(after_routes - before_routes)} / -{len(before_routes - after_routes)}",
    )
    check(
        "selector pre-set leaves the conflict count at zero",
        before_conflicts == after_conflicts == 0,
        f"{before_conflicts} -> {after_conflicts}",
    )
    ic_s.write_file(str(SELECTOR_ASC))
    print(f"  wrote {SELECTOR_ASC}")

    # --- known positive: a second source on the HFOSC global ------------------
    icebox_p, ic_p = load(SELECTOR_ASC)
    graph_p = GlobalDriverGraph(ic_p, icebox_p)
    x, y = PROBE_TILE
    entries, _muxes, bit_to_entries = tile_model(ic_p, x, y)
    bits = signed_tile_bits(ic_p.tile(x, y))
    changed = set(bits)
    changed.discard("!B4[15]")
    changed.add("B4[15]")
    additions, removals = [], []
    for index in bit_to_entries["B4[15]"]:
        entry = entries[index]
        before = all(bit in bits for bit in entry[0])
        after = all(bit in changed for bit in entry[0])
        if after and not before:
            additions.append(entry)
        elif before and not after:
            removals.append(entry)
    model_hit, drivers = graph_p.mutation_creates_multi_driver(x, y, additions, removals)
    base = conflicting_nets(ic_p, icebox_p)
    set_bit(ic_p, x, y, "B4[15]", "1")
    after_count = conflicting_nets(ic_p, icebox_p)
    pll_sources, pll_blocks = pll_driver_state(ic_p, icebox_p)
    identities = {
        driver_identity(
            ic_p,
            icebox_p,
            segment,
            pll_sources,
            pll_blocks,
            spram_driver_state(ic_p),
            oscillator_driver_state(ic_p, pll_sources),
        )
        for segment in drivers
    }

    print(f"\nHFOSC positive: tile=({x},{y}) bit=B4[15]")
    for entry in additions:
        print(f"  add: {entry[2]} -> {entry[3]}")
    print(f"  drivers: {drivers}")
    print(f"  identities: {sorted(i for i in identities if i)}")
    check("exactly one addition, no removal", len(additions) == 1 and not removals)
    check("model reports a conflict", model_hit)
    check(
        "oracle conflict-net delta is +1",
        after_count - base == 1,
        f"delta={after_count - base}",
    )
    check(
        "the HFOSC participates as a source",
        ("hfosc", 19, 31) in identities,
        f"{sorted(i for i in identities if i)}",
    )

    # --- known positive: a second source on the HFOSC fabric output ----------
    print("\n=== the direct fabric output is a source too ===")
    endpoints = oscillator_fabric_endpoints(icebox)
    check(
        "both fabric endpoints come from icebox's cell database, not from here",
        endpoints == {"hfosc": [(0, 28, "slf_op_7")], "lfosc": [(25, 29, "slf_op_0")]},
        f"{endpoints}",
    )
    check(
        "HFOSC annotates its direct fabric output",
        sources.get((0, 28, "slf_op_7")) == ("hfosc", 19, 31),
    )
    check(
        "LFOSC annotates its direct fabric output",
        sources.get((25, 29, "slf_op_0")) == ("lfosc", 6, 31),
    )
    check(
        "each shares the identity of its global path",
        sources.get((0, 28, "slf_op_7")) == sources.get((19, 31, "glb_netwk_4"))
        and sources.get((25, 29, "slf_op_0")) == sources.get((6, 31, "glb_netwk_5")),
        "two paths from one oscillator; separate identities would collide where they meet",
    )
    check(
        "LEDDA's endpoints in the same tile are not swept up with it",
        (0, 28, "slf_op_4") not in sources and (0, 28, "slf_op_6") not in sources,
        "(0,28) hosts both; ownership is by slf_op index, never by tile",
    )

    # Unlike the selector above, this baseline does enable one route: nothing in
    # the fixture drives any destination the fabric segment can reach, so the
    # driver has to be put there.  The invariant asserted is therefore exact
    # identity of the added route, and a conflict count still at zero.
    icebox_f, ic_f = load(ASC)
    px, py, pbit, psource, pdest = FABRIC_PRESET
    before_routes = enabled_routes(ic_f, icebox_f)
    set_bit(ic_f, px, py, pbit, "1")
    after_routes = enabled_routes(ic_f, icebox_f)
    check(
        "the fabric baseline enables exactly the one intended route",
        after_routes - before_routes == {(px, py, psource, pdest)}
        and not (before_routes - after_routes),
        f"+{sorted(after_routes - before_routes)} "
        f"-{len(before_routes - after_routes)}",
    )
    check(
        "and leaves the conflict count at zero",
        conflicting_nets(ic_f, icebox_f) == 0,
    )
    ic_f.write_file(str(FABRIC_SELECTOR_ASC))
    print(f"  wrote {FABRIC_SELECTOR_ASC}")

    icebox_fp, ic_fp = load(FABRIC_SELECTOR_ASC)
    graph_fp = GlobalDriverGraph(ic_fp, icebox_fp)
    fx, fy, fbit, fsource, fdest = FABRIC_FLIP
    f_entries, _f_muxes, f_bit_to_entries = tile_model(ic_fp, fx, fy)
    f_bits = signed_tile_bits(ic_fp.tile(fx, fy))
    f_changed = set(f_bits)
    f_changed.discard(f"!{fbit}")
    f_changed.add(fbit)
    f_additions, f_removals = [], []
    for index in f_bit_to_entries[fbit]:
        entry = f_entries[index]
        was = all(bit in f_bits for bit in entry[0])
        now = all(bit in f_changed for bit in entry[0])
        if now and not was:
            f_additions.append(entry)
        elif was and not now:
            f_removals.append(entry)
    f_hit, f_drivers = graph_fp.mutation_creates_multi_driver(
        fx, fy, f_additions, f_removals
    )
    f_base = conflicting_nets(ic_fp, icebox_fp)
    set_bit(ic_fp, fx, fy, fbit, "1")
    f_after = conflicting_nets(ic_fp, icebox_fp)
    f_pll_sources, f_pll_blocks = pll_driver_state(ic_fp, icebox_fp)
    f_identities = {
        driver_identity(
            ic_fp,
            icebox_fp,
            segment,
            f_pll_sources,
            f_pll_blocks,
            spram_driver_state(ic_fp),
            oscillator_driver_state(ic_fp, f_pll_sources, icebox_fp),
        )
        for segment in f_drivers
    }
    print(f"\nHFOSC fabric positive: tile=({fx},{fy}) bit={fbit}")
    for entry in f_additions:
        print(f"  add: {entry[2]} -> {entry[3]}")
    print(f"  drivers: {f_drivers}")
    print(f"  identities: {sorted(i for i in f_identities if i)}")
    check(
        "exactly one addition, no removal",
        len(f_additions) == 1 and not f_removals and f_additions[0][2] == fsource,
    )
    check("model reports a conflict", f_hit)
    check(
        "oracle conflict-net delta is +1",
        f_after - f_base == 1,
        f"delta={f_after - f_base}",
    )
    check(
        "the HFOSC participates as a source through its fabric output",
        ("hfosc", 19, 31) in f_identities,
        f"{sorted(i for i in f_identities if i)}",
    )
    # The counterfactual, actually run: rebuild the graph with the fabric
    # endpoint's identity withheld and evaluate the same flip.  Asserting only
    # that the identity exists would not show it is what decides the verdict.
    original_state = exhaustive.oscillator_driver_state

    def without_fabric_endpoint(ic_arg, pll_arg, icebox_arg=None):
        sources = original_state(ic_arg, pll_arg, icebox_arg)
        sources.pop((fx, fy, fsource), None)
        return sources

    exhaustive.oscillator_driver_state = without_fabric_endpoint
    try:
        _icebox_cf, ic_cf = load(FABRIC_SELECTOR_ASC)
        graph_cf = GlobalDriverGraph(ic_cf, _icebox_cf)
        cf_hit, cf_drivers = graph_cf.mutation_creates_multi_driver(
            fx, fy, f_additions, f_removals
        )
    finally:
        exhaustive.oscillator_driver_state = original_state
    check(
        "withholding just this endpoint's identity makes the same flip look clean",
        graph_cf.driver_identity((fx, fy, fsource)) is None and not cf_hit,
        f"identity={graph_cf.driver_identity((fx, fy, fsource))}, conflict={cf_hit}, "
        f"drivers={cf_drivers}",
    )
    check(
        "and the global path's identity is untouched by that removal",
        graph_cf.driver_identity((19, 31, "glb_netwk_4")) == ("hfosc", 19, 31),
        "only the fabric endpoint was withheld, so the false negative is localised",
    )

    # --- negative regressions ------------------------------------------------
    print("\n=== negative regressions ===")
    icebox_d, ic_d = load(ASC)
    ic_d.extra_bits = set()
    check(
        "with no padin_glb_netwk bit there is no oscillator identity",
        not oscillator_driver_state(ic_d, {}),
    )

    icebox_h, ic_h = load(ASC)
    ic_h.extra_bits = {
        bit
        for bit in ic_h.extra_bits
        if ic_h.lookup_extra_bit(bit) != ("padin_glb_netwk", "4")
    }
    without_hf = oscillator_driver_state(ic_h, {})
    check(
        "dropping padin 4 removes only the HFOSC annotation",
        (19, 31, "glb_netwk_4") not in without_hf
        and without_hf.get((6, 31, "glb_netwk_5")) == ("lfosc", 6, 31),
    )

    _icebox_l, ic_l = load(ASC.with_name("leds.asc"))
    check(
        "a design with no hard IP gets no oscillator identity",
        not oscillator_driver_state(ic_l, {}),
    )
    check(
        "and in particular no identity on the fabric endpoints",
        (0, 28, "slf_op_7") not in oscillator_driver_state(ic_l, {})
        and (25, 29, "slf_op_0") not in oscillator_driver_state(ic_l, {}),
        "otherwise every design would gain two drivers it does not have",
    )
    check(
        "dropping padin 4 drops the HFOSC fabric endpoint with it",
        (0, 28, "slf_op_7") not in without_hf
        and without_hf.get((25, 29, "slf_op_0")) == ("lfosc", 6, 31),
    )

    _icebox_pll, ic_pll = load(ASC.with_name("pll.asc"))
    pll_only, _blocks = pll_driver_state(ic_pll, _icebox_pll)
    check(
        "a PLL-owned global is not also claimed by an oscillator",
        not oscillator_driver_state(ic_pll, pll_only),
        "padin 7 belongs to the PLL and is not an oscillator index",
    )

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: oscillator fixture, the HFOSC positive, and every negative regression")
    print(
        "Coverage boundary: the HFOSC global and both fabric endpoints.  The LFOSC "
        "global's fabout sits in io "
        "tile (12,0), which package sg48 does not bond out, so no LUT output can "
        "be brought to that mux and no second source can be constructed there.  "
        "SB_I2C and SB_SPI have their own fixtures (make i2c-check, "
        "make spi-check).  LEDDA is still unmodelled; SB_RGBA_DRV has no "
        "fabric-facing output and is not applicable to the driver graph."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

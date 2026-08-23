#!/usr/bin/env python3
"""Named regressions for the PLL fixture's hard-IP driver identity.

Everything here is host-only.  The fixture exists because `leds` and `dense`
instantiate no hard IP at all, so neither of them can exercise a source that is
not a LUT, an IO input pad, a RAM read port or a DSP output.

Two facts about IceStorm drive the whole design:

  * a PLL output is delivered through the IO tile that `pllinfo_db` assigns to
    that output, so a model that only pattern-matches `io_*/D_IN_*` counts it by
    accident, without ever reading the PLL configuration;
  * a PLL global output reaches `glb_netwk_*` without any source segment in the
    graph, so before this identity existed that whole net was driverless and a
    second source added to it produced no conflict at all.

The mutations below are checked twice: once through
`exhaustive.GlobalDriverGraph` (the incremental model) and once by mutating the
configuration and rebuilding IceStorm's entire segment graph, which shares no
conflict logic with it.
"""

from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from exhaustive import GlobalDriverGraph, tile_model  # noqa: E402
from iceutil import (  # noqa: E402
    assert_tile_coverage,
    configuration_tiles,
    load_icebox,
    signed_tile_bits,
)
from oracle import conflicting_nets, driver_identity, pll_driver_state  # noqa: E402

ASC = Path(sys.argv[1] if len(sys.argv) > 1 else "build/pll.asc")
SELECTOR_ASC = ASC.with_name("pll_selector.asc")

PLLTYPE_NAMES = {
    "000": "DISABLED",
    "010": "SB_PLL40_PAD",
    "100": "SB_PLL40_2_PAD",
    "110": "SB_PLL40_2F_PAD",
    "011": "SB_PLL40_CORE",
    "111": "SB_PLL40_2F_CORE",
}

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


def pll_config_bit(ic, icebox, name):
    info = icebox.pllinfo_db[ic.pll_list()[0]]
    x, y, bit_name = info[name]
    for entry in ic.tile_db(x, y):
        if entry[1] == "PLL" and entry[2] == bit_name:
            row, column = entry[0][0][1:].rstrip("]").split("[")
            return (x, y, int(row), int(column))
    raise KeyError(name)


def pll_field(ic, icebox, prefix, width):
    bits = []
    for index in range(width):
        x, y, row, column = pll_config_bit(ic, icebox, f"{prefix}_{index}")
        bits.append(ic.tile(x, y)[row][column])
    return "".join(reversed(bits))


def enabled_routes(ic, icebox):
    """Every routing/buffer entry the configuration currently enables."""
    routes = set()
    assert_tile_coverage(ic)
    for _collection, (x, y), tile in configuration_tiles(ic):
        config = icebox.tileconfig(tile)
        for entry in ic.tile_db(x, y):
            if entry[1] not in ("routing", "buffer"):
                continue
            if not ic.tile_has_net(x, y, entry[2]) or not ic.tile_has_net(
                x, y, entry[3]
            ):
                continue
            if config.match(entry[0]):
                routes.add((x, y, entry[2], entry[3]))
    return routes


def flip_delta(ic, x, y, row, column):
    """Return the (additions, removals) a single-bit flip causes in one tile."""
    entries, _muxes, bit_to_entries = tile_model(ic, x, y)
    tile = ic.logic_tiles[(x, y)] if (x, y) in ic.logic_tiles else ic.tile(x, y)
    bits = signed_tile_bits(tile)
    name = f"B{row}[{column}]"
    was_one = tile[row][column] == "1"
    changed = set(bits)
    changed.discard(("" if was_one else "!") + name)
    changed.add(("!" if was_one else "") + name)
    additions, removals = [], []
    for index in bit_to_entries.get(name, ()):
        entry = entries[index]
        before = all(bit in bits for bit in entry[0])
        after = all(bit in changed for bit in entry[0])
        if after and not before:
            additions.append(entry)
        elif before and not after:
            removals.append(entry)
    return additions, removals


def flip_in_place(ic, x, y, row, column):
    tile = ic.tile(x, y)
    original = tile[row]
    tile[row] = original[:column] + ("0" if original[column] == "1" else "1") + original[
        column + 1 :
    ]
    return original


def named_positive(label, path, x, y, row, column, expect_identity):
    """Model and full-rebuild oracle must both call this flip a conflict."""
    icebox, ic = load(path)
    graph = GlobalDriverGraph(ic, icebox)
    base = conflicting_nets(ic, icebox)
    additions, removals = flip_delta(ic, x, y, row, column)
    model_hit, drivers = graph.mutation_creates_multi_driver(x, y, additions, removals)

    original = flip_in_place(ic, x, y, row, column)
    after = conflicting_nets(ic, icebox)
    sources, blocks = pll_driver_state(ic, icebox)
    identities = {
        driver_identity(ic, icebox, segment, sources, blocks) for segment in drivers
    }
    ic.tile(x, y)[row] = original

    print(f"\n{label}: tile=({x},{y}) bit=B{row}[{column}]")
    for entry in additions:
        print(f"  add: {entry[2]} -> {entry[3]}")
    print(f"  drivers: {drivers}")
    print(f"  identities: {sorted(i for i in identities if i)}")
    check(f"{label}: baseline has no conflicting net", base == 0, f"base={base}")
    check(f"{label}: model reports a conflict", model_hit)
    check(
        f"{label}: oracle conflict-net delta is +1",
        after - base == 1,
        f"delta={after - base}",
    )
    check(
        f"{label}: expected source {expect_identity} participates",
        expect_identity in identities,
        f"got {sorted(i for i in identities if i)}",
    )
    check(f"{label}: exactly one addition, no removal", len(additions) == 1 and not removals)


def main() -> int:
    icebox, ic = load(ASC)

    print("=== fixture really enables the PLL (read from configuration bits) ===")
    pll_type = pll_field(ic, icebox, "PLLTYPE", 3)
    check(
        f"PLLTYPE={pll_type} is {PLLTYPE_NAMES.get(pll_type)}",
        pll_type == "110",
        "expected SB_PLL40_2F_PAD",
    )
    for field, width, expected in (
        ("FEEDBACK_PATH", 3, "001"),
        ("DIVR", 4, "0000"),
        ("DIVF", 7, "0111111"),
        ("DIVQ", 3, "100"),
        ("FILTER_RANGE", 3, "001"),
    ):
        value = pll_field(ic, icebox, field, width)
        check(f"{field}={value}", value == expected, f"expected {expected}")

    graph = GlobalDriverGraph(ic, icebox)
    sources, blocks = pll_driver_state(ic, icebox)
    print("\n=== configured PLL source endpoints ===")
    for segment, identity in sorted(sources.items()):
        print(f"  {segment} -> {identity}")
    check("baseline model has no multi-driver net", graph.base_multi_driver_nets == 0)
    check(
        "port A core and global share one identity",
        sources.get((12, 31, "io_1/D_IN_0")) == sources.get((12, 31, "glb_netwk_7")),
        "core and global are two paths of one physical output",
    )
    check(
        "port B core endpoint is a PLL source",
        sources.get((13, 31, "io_0/D_IN_0")) == ("pll", 12, 31, "B"),
    )
    check(
        "glb_netwk_2 is not annotated (port B global unused)",
        (13, 31, "glb_netwk_2") not in sources,
    )
    check(
        "PLL-owned IO blocks do not also carry an ordinary IO identity",
        all(
            driver_identity(ic, icebox, (x, y, f"io_{block}/D_IN_1"), sources, blocks)
            is None
            for (x, y, block) in blocks
        ),
    )

    # --- known positive 1: the core path -------------------------------------
    named_positive(
        "CORE positive", ASC, 12, 30, 12, 53, ("pll", 12, 31, "B")
    )

    # --- selector pre-set, generated and verified, never hand-edited ---------
    print("\n=== generating the GLOBAL test baseline ===")
    icebox_s, ic_s = load(ASC)
    before_routes = enabled_routes(ic_s, icebox_s)
    before_conflicts = conflicting_nets(ic_s, icebox_s)
    flip_in_place(ic_s, 19, 0, 5, 15)
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

    # --- known positive 2: the global path -----------------------------------
    named_positive(
        "GLOBAL positive", SELECTOR_ASC, 19, 0, 4, 15, ("pll", 12, 31, "A")
    )

    # --- negative regressions ------------------------------------------------
    print("\n=== negative regressions ===")
    icebox_d, ic_d = load(ASC)
    for index in range(3):
        x, y, row, column = pll_config_bit(ic_d, icebox_d, f"PLLTYPE_{index}")
        tile = ic_d.tile(x, y)
        tile[row] = tile[row][:column] + "0" + tile[row][column + 1 :]
    disabled_sources, disabled_blocks = pll_driver_state(ic_d, icebox_d)
    check(
        "PLLTYPE=000 produces no PLL identity anywhere",
        not disabled_sources and not disabled_blocks,
        f"{sorted(disabled_sources)}",
    )

    icebox_g, ic_g = load(ASC)
    ic_g.extra_bits = {
        bit
        for bit in ic_g.extra_bits
        if ic_g.lookup_extra_bit(bit) != ("padin_glb_netwk", "7")
    }
    without_global, _blocks = pll_driver_state(ic_g, icebox_g)
    check(
        "removing padin_glb_netwk 7 drops the global annotation",
        (12, 31, "glb_netwk_7") not in without_global,
    )
    check(
        "removing padin_glb_netwk 7 keeps the core annotation",
        without_global.get((12, 31, "io_1/D_IN_0")) == ("pll", 12, 31, "A"),
    )

    merged = {sources[(12, 31, "io_1/D_IN_0")], sources[(12, 31, "glb_netwk_7")]}
    check(
        "merging one port's core and global components yields a single identity",
        len(merged) == 1,
        f"{merged}",
    )

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: PLL fixture, both named positives, and every negative regression")
    print(
        "Coverage boundary: UP5K SB_PLL40_2F_PAD, port A global and port B core. "
        "Port A core and the other PLL variants are not exercised; icebox_vlog "
        "names a PAD-型 PLL's port A core output io_N/PAD while this model "
        "annotates io_N/D_IN_0. SPRAM and the on-chip oscillators have their own "
        "fixtures (make spram-check, make osc-check); the remaining hard IP -- "
        "I2C, SPI and the RGB drivers -- is not modelled."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

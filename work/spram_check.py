#!/usr/bin/env python3
"""Named regressions for the SPRAM fixture's hard-IP driver identity.

Host-only.  This is the second hard-IP fixture; the first is `pll_check.py`.

The gap it closes: UP5K single-port RAM read data leaves the hard IP through
`slf_op_*` segments on ipcon tiles.  That name appears nowhere in a design
without hard IP -- `leds` and `dense` contain none of them -- so a driver
whitelist built around `lutff_*/out`, `io_*/D_IN_*`, `ram/RDATA_*` and
`mult/O_*` never matched it, and all sixteen read-data outputs looked like
undriven nets.  A second source routed onto one of them produced no conflict.

Layout facts, measured rather than assumed, by placing one and then four
SB_SPRAM256KA instances:

  * one instance  -> `CBIT_0` set in ipcon tile (0,1); `slf_op_0..7` present on
    tiles (0,1) and (0,2), i.e. sixteen outputs = DATAOUT[15:0];
  * four instances -> `CBIT_0` and `CBIT_1` set in both (0,1) and (25,1), with
    `slf_op_0..7` on rows 1..4 of both ipcon columns.

So each ipcon column holds two instances: `CBIT_0` enables the one occupying
rows 1 and 2, `CBIT_1` the one occupying rows 3 and 4.
"""

from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from exhaustive import GlobalDriverGraph, tile_model  # noqa: E402
from iceutil import load_icebox, signed_tile_bits  # noqa: E402
from oracle import (  # noqa: E402
    conflicting_nets,
    driver_identity,
    ipconfig_bit,
    pll_driver_state,
    spram_driver_state,
)

ASC = Path(sys.argv[1] if len(sys.argv) > 1 else "build/spram.asc")
LEDS_ASC = ASC.with_name("leds.asc")

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


def flip_delta(ic, x, y, row, column):
    entries, _muxes, bit_to_entries = tile_model(ic, x, y)
    tile = ic.logic_tiles[(x, y)]
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


def main() -> int:
    icebox, ic = load(ASC)

    print("=== fixture really instantiates an SPRAM (read from configuration) ===")
    enables = {
        (x, cbit): ipconfig_bit(ic, x, 1, f"CBIT_{cbit}")
        for x in sorted({tile_x for tile_x, _ in ic.ipcon_tiles})
        for cbit in (0, 1)
    }
    print(f"  ipcon enable bits: {enables}")
    check("column 0 instance 0 is enabled", enables.get((0, 0)) == "1")
    check(
        "the other three instances are disabled",
        all(value != "1" for key, value in enables.items() if key != (0, 0)),
        f"{enables}",
    )

    graph = GlobalDriverGraph(ic, icebox)
    sources = spram_driver_state(ic)
    tiles_used = sorted({(x, y) for (x, y, _name) in sources})
    print(f"\n  SPRAM source endpoints: {len(sources)} on tiles {tiles_used}")
    check("sixteen read-data outputs are annotated", len(sources) == 16)
    check("they sit on rows 1 and 2 of column 0", tiles_used == [(0, 1), (0, 2)])
    check(
        "every output bit is its own identity",
        len(set(sources.values())) == 16,
        "DATAOUT bits are separate physical drivers, so no aliasing",
    )
    check("model baseline has no multi-driver net", graph.base_multi_driver_nets == 0)
    check("oracle baseline has no conflicting net", conflicting_nets(ic, icebox) == 0)

    # --- known positive ------------------------------------------------------
    x, y, row, column = 1, 1, 1, 48
    additions, removals = flip_delta(ic, x, y, row, column)
    model_hit, drivers = graph.mutation_creates_multi_driver(x, y, additions, removals)
    base = conflicting_nets(ic, icebox)
    tile = ic.logic_tiles[(x, y)]
    original = tile[row]
    tile[row] = original[:column] + ("0" if original[column] == "1" else "1") + original[
        column + 1 :
    ]
    after = conflicting_nets(ic, icebox)
    pll_sources, pll_blocks = pll_driver_state(ic, icebox)
    identities = {
        driver_identity(ic, icebox, segment, pll_sources, pll_blocks, sources)
        for segment in drivers
    }
    tile[row] = original

    print(f"\nSPRAM positive: tile=({x},{y}) bit=B{row}[{column}]")
    for entry in additions:
        print(f"  add: {entry[2]} -> {entry[3]}")
    print(f"  drivers: {drivers}")
    print(f"  identities: {sorted(i for i in identities if i)}")
    check("exactly one addition, no removal", len(additions) == 1 and not removals)
    check("model reports a conflict", model_hit)
    check("oracle conflict-net delta is +1", after - base == 1, f"delta={after - base}")
    check(
        "an SPRAM read-data output participates",
        ("spram", 0, 2, 7) in identities,
        f"{sorted(i for i in identities if i)}",
    )

    # --- negative regressions ------------------------------------------------
    print("\n=== negative regressions ===")
    icebox_d, ic_d = load(ASC)
    for entry in ic_d.tile_db(0, 1):
        if entry[1] == "IpConfig" and len(entry) > 2 and entry[2] == "CBIT_0":
            r, c = entry[0][0][1:].rstrip("]").split("[")
            tile = ic_d.ipcon_tiles[(0, 1)]
            tile[int(r)] = tile[int(r)][: int(c)] + "0" + tile[int(r)][int(c) + 1 :]
    check(
        "clearing CBIT_0 removes every SPRAM identity",
        not spram_driver_state(ic_d),
        f"{sorted(spram_driver_state(ic_d))[:3]}",
    )

    check(
        "the disabled instance's rows carry no identity",
        all((0, y) not in {(sx, sy) for (sx, sy, _n) in sources} for y in (3, 4)),
    )

    if LEDS_ASC.exists():
        _icebox_l, ic_l = load(LEDS_ASC)
        check(
            "a design without hard IP gets no SPRAM identity",
            not spram_driver_state(ic_l),
        )
        check(
            "and has no slf_op segment at all",
            not any(
                "slf_op" in segment[2]
                for group in ic_l.group_segments()
                for segment in group
            ),
        )

    check(
        "an slf_op segment on a disabled bank resolves to None",
        driver_identity(ic_d, icebox_d, (0, 1, "slf_op_0")) is None,
    )

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: SPRAM fixture, the named positive, and every negative regression")
    print(
        "Coverage boundary: one SB_SPRAM256KA in ipcon column 0, read-data path "
        "only.  The write path, the second instance per column and the "
        "right-hand column are not exercised.  The PLL and the on-chip "
        "oscillators have their own fixtures, as do SB_I2C and SB_SPI.  LEDDA "
        "is not modelled -- its enable state is not a configuration fact -- and "
        "SB_RGBA_DRV has no fabric-facing output and is not applicable to the "
        "driver graph."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

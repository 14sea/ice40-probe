#!/usr/bin/env python3
"""Named regressions for the SB_I2C driver identity.

Host-only.  Fourth hard-IP fixture, after `pll_check.py`, `spram_check.py` and
`osc_check.py`, and the first one written after the hard-IP inventory
(`make hard-ip-inventory`), which is what established that this block is worth
a fixture at all.

The gap: each SB_I2C has fifteen outputs that leave the hard IP through
`slf_op_*` segments on ipcon tiles.  That is the same segment class as SPRAM
read data and invisible for the same reason -- a whitelist of `lutff_*/out`,
`io_*/D_IN_*`, `ram/RDATA_*` and `mult/O_*` never matches it -- so every I2C
output net was a net with no source, and a second driver routed onto one
produced no conflict.

Measured rather than assumed:

  * both instances are enumerated from the cell database, not from a design.
    Their configuration is not symmetric: the left instance's two enabling bits
    sit in IO tiles (13,31) and (12,31), the right instance's both sit in
    (19,31).  A fixture with one instance would have tested half of that.
  * the enabling bits are set in the built design and clear in `leds.asc`.
    Without the second half, "the bit is 1" could just mean the bit is always 1.
  * the bits are set for a placed instance whether SCLI/SDAI come from the
    dedicated pads or, as in this fixture, from fabric registers.  So they mark
    an enabled instance, not a pad mux.

Not resolved, and deliberately not guessed: what each of the two bits means on
its own.  nextpnr writes them together and no public document separates them,
so a configuration with exactly one set is reported as UNDETERMINED rather than
being read as enabled (which would invent fifteen drivers) or as disabled
(which would hide them).  Both bits live in IO tiles, outside the logic-tile
scope of every sweep here, so nothing in this project can produce that state by
accident.
"""

from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import exhaustive  # noqa: E402
from exhaustive import (  # noqa: E402
    GlobalDriverGraph,
    i2c_cells,
    i2c_enable_bits,
    i2c_fabric_endpoints,
    ipconfig_bit,
    tile_model,
)
from iceutil import load_icebox, signed_tile_bits  # noqa: E402
import oracle  # noqa: E402
from oracle import conflicting_nets, driver_identity  # noqa: E402

ASC = Path(sys.argv[1] if len(sys.argv) > 1 else "build/i2c.asc")
LEDS_ASC = ASC.with_name("leds.asc")
OSC_ASC = ASC.with_name("osc.asc")

LEFT = (0, 31, 0)
RIGHT = (25, 31, 0)

# Two named positives, one per instance.  Neither needs a generated baseline:
# unlike the oscillator's fabric endpoint, the fixture already drives LUTs
# whose spans these muxes reach, so the second source is there to begin with.
# The right-hand one is on tile (25,29) on purpose -- the LFOSC's direct fabric
# output is `slf_op_0` of that same tile, so a tile-level ownership rule would
# hand this flip to the wrong block.
POSITIVES = (
    ("left", 0, 30, "B1[52]", "slf_op_0", "sp4_r_v_b_1", ("i2c", 0, 31, "SBDATO2")),
    ("right", 25, 29, "B3[48]", "slf_op_1", "sp4_v_b_18", ("i2c", 25, 31, "SDAO")),
)

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


def set_ipconfig_bit(ic, x, y, name, value) -> None:
    """Write one named IpConfig bit, located through the tile database."""
    for entry in ic.tile_db(x, y):
        if entry[1] == "IpConfig" and len(entry) > 2 and entry[2] == name:
            row, column = entry[0][0][1:].rstrip("]").split("[")
            row, column = int(row), int(column)
            tile = ic.tile(x, y)
            tile[row] = tile[row][:column] + value + tile[row][column + 1 :]
            return
    raise KeyError(f"no IpConfig bit {name} in tile ({x},{y})")


def flip_delta(ic, x, y, bit_name):
    """The routing entries a single 0 -> 1 flip adds and removes in one tile."""
    entries, _muxes, bit_to_entries = tile_model(ic, x, y)
    bits = signed_tile_bits(ic.tile(x, y))
    changed = set(bits)
    changed.discard(f"!{bit_name}")
    changed.add(bit_name)
    additions, removals = [], []
    for index in bit_to_entries.get(bit_name, ()):
        entry = entries[index]
        was = all(bit in bits for bit in entry[0])
        now = all(bit in changed for bit in entry[0])
        if now and not was:
            additions.append(entry)
        elif was and not now:
            removals.append(entry)
    return additions, removals


def raises(action) -> tuple[bool, str]:
    """Run `action` and report whether it refused with a RuntimeError."""
    try:
        action()
    except RuntimeError as error:
        return True, str(error)
    return False, ""


def set_bit(ic, x, y, name, value) -> None:
    row, column = name[1:].rstrip("]").split("[")
    row, column = int(row), int(column)
    tile = ic.tile(x, y)
    tile[row] = tile[row][:column] + value + tile[row][column + 1 :]


def main() -> int:
    icebox, ic = load(ASC)
    cells = dict(i2c_cells(icebox))

    print("=== both instances are enabled (read from configuration) ===")
    check(
        "the database knows two SB_I2C instances",
        sorted(cells) == [LEFT, RIGHT],
        f"{sorted(cells)}",
    )
    _leds_icebox, ic_leds = load(LEDS_ASC)
    for placement in (LEFT, RIGHT):
        for x, y, name in i2c_enable_bits(cells[placement]):
            check(
                f"{placement}: {name} at ({x},{y}) is set",
                ipconfig_bit(ic, x, y, name) == "1",
                f"read {ipconfig_bit(ic, x, y, name)!r}",
            )
            # Without the negative control this would also pass on a bit that
            # is simply always 1, and would prove nothing about the instance.
            check(
                f"{placement}: and clear in a design without the IP",
                ipconfig_bit(ic_leds, x, y, name) == "0",
                f"read {ipconfig_bit(ic_leds, x, y, name)!r}",
            )
            check(
                f"{placement}: {name} lives in an IO tile, outside every sweep",
                (x, y) in ic.io_tiles,
                "the sweeps flip logic tiles only, so no sweep can reach this bit",
            )
    check(
        "the two instances' bits are laid out differently",
        len({(x, y) for x, y, _n in i2c_enable_bits(cells[LEFT])}) == 2
        and len({(x, y) for x, y, _n in i2c_enable_bits(cells[RIGHT])}) == 1,
        "left: two IO tiles; right: one -- a one-instance fixture misses this",
    )

    graph = GlobalDriverGraph(ic, icebox)
    sources = graph.i2c_sources
    expected = {
        segment: ("i2c", placement[0], placement[1], port)
        for placement, cell in cells.items()
        for segment, port in i2c_fabric_endpoints(cell).items()
    }
    print(f"\n  I2C source endpoints: {len(sources)}")
    # Both directions.  A one-sided check passes with half the endpoints
    # missing, which is exactly how the SPI count came out as 19 instead of 25.
    check(
        "every endpoint the database states is annotated",
        not (expected.keys() - sources.keys()),
        f"{sorted(expected.keys() - sources.keys())[:3]}",
    )
    check(
        "and nothing the database does not state is",
        not (sources.keys() - expected.keys()),
        f"{sorted(sources.keys() - expected.keys())[:3]}",
    )
    check("the annotations agree port by port", sources == expected)
    check(
        "each output port is its own identity",
        len(set(sources.values())) == 30,
        f"{len(set(sources.values()))} identities for {len(sources)} endpoints",
    )
    present = {
        segment
        for group in ic.group_segments()
        for segment in group
        if "slf_op" in segment[2]
    }
    # The annotation is derived from the database, so comparing it with the
    # database cannot notice an output that stopped being routed.  This looks
    # at the design's own segment graph instead: an unrouted output would leave
    # its identity unexercised and the fixture quietly hollow.
    check(
        "all thirty endpoints actually appear in the design's segment graph",
        not (expected.keys() - present),
        f"{sorted(expected.keys() - present)[:3]} missing of {len(present)} present",
    )
    check(
        "no instance is in an undetermined enable state",
        not graph.i2c_undetermined,
        f"{graph.i2c_undetermined}",
    )
    check(
        "the independent oracle derives the same annotation",
        oracle.i2c_driver_state(ic, icebox) == sources,
        "two derivations from the cell database, neither importing the other",
    )
    check("model baseline has no multi-driver net", graph.base_multi_driver_nets == 0)
    check("oracle baseline has no conflicting net", conflicting_nets(ic, icebox) == 0)

    print("\n=== ownership is by port, never by tile ===")
    check(
        "LEDDA's LEDDON shares tile (0,29) and is not claimed",
        (0, 29, "slf_op_0") not in sources and (0, 29, "slf_op_1") in sources,
        "(0,29) carries LEDDON plus seven I2C outputs",
    )
    check(
        "the LFOSC's fabric output shares tile (25,29) and is not claimed",
        (25, 29, "slf_op_0") not in sources and (25, 29, "slf_op_1") in sources,
        "(25,29) carries CLKLF_FABRIC plus seven I2C outputs",
    )
    _osc_icebox, ic_osc = load(OSC_ASC)
    check(
        "and in the oscillator fixture that same segment belongs to the LFOSC",
        oracle.oscillator_driver_state(ic_osc, {}).get((25, 29, "slf_op_0"))
        == ("lfosc", 6, 31),
        "the two blocks are distinguished by index, and both annotations exist",
    )

    print("\n=== the overlap guard has to be able to fire ===")
    # A guard no fixture can trigger proves nothing.  The oscillator fixture is
    # the one configuration where another block owns a segment an I2C could
    # plausibly be given, so the claim is injected there deliberately.
    icebox_g, ic_g = load(OSC_ASC)
    built, _message = raises(lambda: GlobalDriverGraph(ic_g, icebox_g))
    check(
        "the oscillator fixture builds cleanly on its own",
        not built,
        "so the failure below is caused by the injection, not by the fixture",
    )
    original_state = exhaustive.i2c_driver_state
    contested = (25, 29, "slf_op_0")

    def with_overlapping_claim(ic_arg, icebox_arg=None):
        state = original_state(ic_arg, icebox_arg)
        state[contested] = ("i2c", 25, 31, "INJECTED")
        return state

    exhaustive.i2c_driver_state = with_overlapping_claim
    try:
        icebox_o, ic_o = load(OSC_ASC)
        fired, message = raises(lambda: GlobalDriverGraph(ic_o, icebox_o))
    finally:
        exhaustive.i2c_driver_state = original_state
    check(
        "an I2C claim on the LFOSC's fabric output is refused, not silently won",
        fired and "slf_op_0" in message,
        message or "no RuntimeError raised",
    )

    # --- known positives, one per instance ------------------------------------
    for label, x, y, bit_name, source, destination, identity in POSITIVES:
        icebox_p, ic_p = load(ASC)
        graph_p = GlobalDriverGraph(ic_p, icebox_p)
        additions, removals = flip_delta(ic_p, x, y, bit_name)
        model_hit, drivers = graph_p.mutation_creates_multi_driver(
            x, y, additions, removals
        )
        base = conflicting_nets(ic_p, icebox_p)
        set_bit(ic_p, x, y, bit_name, "1")
        after = conflicting_nets(ic_p, icebox_p)
        identities = {
            driver_identity(ic_p, icebox_p, segment) for segment in drivers
        }
        print(f"\nI2C positive ({label}): tile=({x},{y}) bit={bit_name}")
        for entry in additions:
            print(f"  add: {entry[2]} -> {entry[3]}")
        print(f"  drivers: {drivers}")
        print(f"  identities: {sorted(i for i in identities if i)}")
        check(
            f"{label}: exactly one addition, no removal",
            len(additions) == 1
            and not removals
            and additions[0][2] == source
            and additions[0][3] == destination,
            f"{[(e[2], e[3]) for e in additions]} / {len(removals)} removals",
        )
        check(f"{label}: model reports a conflict", model_hit)
        check(
            f"{label}: oracle conflict-net delta is +1",
            after - base == 1,
            f"delta={after - base}",
        )
        check(
            f"{label}: the I2C output participates as a source",
            identity in identities,
            f"{sorted(i for i in identities if i)}",
        )

    # --- the whole positive class of this fixture, not just the named two -----
    #
    # Two named cases show the identity works somewhere.  They do not show that
    # the model and the whole-graph oracle agree wherever it applies, and a
    # sample of two has no power to find a disagreement.  This class is small
    # enough to enumerate exhaustively, so it is.
    print("\n=== every conflict-creating single-bit flip out of an I2C output ===")
    icebox_c, ic_c = load(ASC)
    graph_c = GlobalDriverGraph(ic_c, icebox_c)
    positives = []
    for x, y in sorted({(sx, sy) for sx, sy, _n in graph_c.i2c_sources}):
        entries, _muxes, bit_to_entries = tile_model(ic_c, x, y)
        tile = ic_c.tile(x, y)
        for row, line in enumerate(tile):
            for column, value in enumerate(line):
                if value != "0":
                    continue
                bit_name = f"B{row}[{column}]"
                if bit_name not in bit_to_entries:
                    continue
                additions, removals = flip_delta(ic_c, x, y, bit_name)
                if len(additions) != 1 or removals:
                    continue
                if (x, y, additions[0][2]) not in graph_c.i2c_sources:
                    continue
                hit, _drivers = graph_c.mutation_creates_multi_driver(
                    x, y, additions, removals
                )
                if hit:
                    positives.append((x, y, bit_name, additions, removals))
    check(
        "the model finds 23 of them",
        len(positives) == 23,
        f"{len(positives)}: "
        f"{sorted({(x, y) for x, y, _b, _a, _r in positives})}",
    )
    check(
        "both named positives are members of that class",
        {(POSITIVES[0][1], POSITIVES[0][2], POSITIVES[0][3]),
         (POSITIVES[1][1], POSITIVES[1][2], POSITIVES[1][3])}
        <= {(x, y, bit) for x, y, bit, _a, _r in positives},
    )
    base = conflicting_nets(ic_c, icebox_c)
    deltas = []
    for x, y, bit_name, additions, removals in positives:
        set_bit(ic_c, x, y, bit_name, "1")
        deltas.append(conflicting_nets(ic_c, icebox_c) - base)
        set_bit(ic_c, x, y, bit_name, "0")
    check(
        "the whole-graph oracle confirms every one of them, each +1",
        deltas == [1] * len(positives),
        f"{sorted(set(deltas))}",
    )

    # --- the counterfactual, actually run ------------------------------------
    print("\n=== withholding one endpoint's identity ===")
    label, x, y, bit_name, source, _destination, identity = POSITIVES[0]
    icebox_p, ic_p = load(ASC)
    additions, removals = flip_delta(ic_p, x, y, bit_name)
    original_state = exhaustive.i2c_driver_state

    def without_one_endpoint(ic_arg, icebox_arg=None):
        state = original_state(ic_arg, icebox_arg)
        state.pop((x, y, source), None)
        return state

    exhaustive.i2c_driver_state = without_one_endpoint
    try:
        icebox_cf, ic_cf = load(ASC)
        graph_cf = GlobalDriverGraph(ic_cf, icebox_cf)
        cf_hit, cf_drivers = graph_cf.mutation_creates_multi_driver(
            x, y, additions, removals
        )
    finally:
        exhaustive.i2c_driver_state = original_state
    check(
        "withholding just this endpoint makes the same flip look clean",
        graph_cf.driver_identity((x, y, source)) is None and not cf_hit,
        f"identity={graph_cf.driver_identity((x, y, source))}, conflict={cf_hit}, "
        f"drivers={cf_drivers}",
    )
    check(
        "and the other twenty-nine endpoints keep their identities",
        len(graph_cf.i2c_sources) == 29
        and graph_cf.driver_identity((0, 30, "slf_op_1")) == ("i2c", 0, 31, "SBDATO3"),
        "the false negative is localised, not global",
    )

    # --- negative regressions -------------------------------------------------
    print("\n=== negative regressions ===")
    check(
        "a design without hard IP gets no I2C identity",
        not exhaustive.i2c_driver_state(ic_leds, icebox),
    )
    check(
        "and has no slf_op segment at all",
        not any(
            "slf_op" in segment[2]
            for group in ic_leds.group_segments()
            for segment in group
        ),
    )

    icebox_off, ic_off = load(ASC)
    for x_bit, y_bit, name in i2c_enable_bits(cells[LEFT]):
        set_ipconfig_bit(ic_off, x_bit, y_bit, name, "0")
    off_sources = exhaustive.i2c_driver_state(ic_off, icebox_off)
    check(
        "clearing both of an instance's enable bits removes its identities",
        not any(identity[1:3] == LEFT[:2] for identity in off_sources.values()),
        f"{sorted({i for i in off_sources.values() if i[1:3] == LEFT[:2]})[:2]}",
    )
    check(
        "the other instance is untouched",
        len(off_sources) == 15
        and all(identity[1:3] == RIGHT[:2] for identity in off_sources.values()),
        f"{len(off_sources)} endpoints left",
    )
    check(
        "a disabled instance's slf_op resolves to None",
        driver_identity(ic_off, icebox_off, (0, 30, "slf_op_0")) is None,
    )
    check(
        "and a disabled instance is not reported as undetermined",
        not exhaustive.i2c_undetermined(ic_off, icebox_off),
        "both bits clear is a determined answer: off",
    )

    icebox_mixed, ic_mixed = load(ASC)
    first_bit = i2c_enable_bits(cells[LEFT])[0]
    set_ipconfig_bit(ic_mixed, *first_bit[:2], first_bit[2], "0")
    mixed_sources = exhaustive.i2c_driver_state(ic_mixed, icebox_mixed)
    check(
        "clearing exactly one bit is reported as undetermined",
        exhaustive.i2c_undetermined(ic_mixed, icebox_mixed) == [LEFT],
        f"{exhaustive.i2c_undetermined(ic_mixed, icebox_mixed)}",
    )
    check(
        "the oracle reports the same undetermined instance",
        oracle.i2c_undetermined(ic_mixed, icebox_mixed) == [LEFT],
        f"{oracle.i2c_undetermined(ic_mixed, icebox_mixed)}",
    )
    check(
        "an undetermined instance is given no identity either way",
        not any(identity[1:3] == LEFT[:2] for identity in mixed_sources.values())
        and len(mixed_sources) == 15,
        "claiming it drives would invent fifteen drivers; claiming it does not "
        "would hide them",
    )
    # Reporting the unknown is not enough.  If the graph still built and still
    # answered, the unknown would reach the caller as "no conflict" -- fifteen
    # drivers quietly absent from a clean-looking baseline.  Both verdict
    # layers refuse.
    fired, message = raises(lambda: GlobalDriverGraph(ic_mixed, icebox_mixed))
    check(
        "the model refuses to build a verdict on an undetermined instance",
        fired and str(LEFT) in message,
        message or "the graph was built and reported a baseline anyway",
    )
    fired, message = raises(lambda: conflicting_nets(ic_mixed, icebox_mixed))
    check(
        "and the oracle refuses to count conflicts on one",
        fired and str(LEFT) in message,
        message or "the oracle returned a count anyway",
    )
    # Discrimination: it is the mixed state that is refused, not any edit.
    refused_off, _message = raises(lambda: GlobalDriverGraph(ic_off, icebox_off))
    check(
        "a fully disabled instance is still answerable",
        not refused_off and conflicting_nets(ic_off, icebox_off) == 0,
        "off is a determined answer, so the verdict layer still works",
    )

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: I2C fixture, both named positives, and every negative regression")
    print(
        "Coverage boundary: the fifteen fabric outputs of each of the two "
        "SB_I2C instances, gated on the enable bits the cell database names.  "
        "The IP's inputs, its register semantics, and what either enable bit "
        "means on its own are outside it.  SPI, LEDDA and the RGB drivers "
        "remain unmodelled; LEDDA in particular has no enabling bit at all, so "
        "its state is not a configuration fact."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

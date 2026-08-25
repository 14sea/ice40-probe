#!/usr/bin/env python3
"""Named regressions for the SB_SPI driver identity.

Host-only.  Fifth hard-IP fixture, after PLL, SPRAM, the oscillators and I2C.

The gap is the one SPRAM and I2C had: each SB_SPI has twenty-five outputs that
leave the block through `slf_op_*` segments on ipcon tiles, which a whitelist
of `lutff_*/out`, `io_*/D_IN_*`, `ram/RDATA_*` and `mult/O_*` never matches, so
every SPI output net was a net with no source and a second driver routed onto
one produced no conflict.

Twenty-five, not nineteen.  The inventory's first pass measured nineteen off a
design that connected one chip select out of four; the count was a property of
that Verilog, not of the block.  Endpoints are taken from the cell database and
compared with the design in both directions, and the design's own segment graph
is checked as well -- comparing the database with itself could not notice an
output that stopped being routed.

`work/spi_evidence.py` (`make spi-evidence`) rebuilds the two facts underneath
this one: which BUS_ADDR74 values nextpnr accepts and which instance each
selects, enumerated over all sixteen four-bit values; and the enable vector a
placed instance writes, read back per instance with a no-SPI negative control.

What an individual SPI_ENABLE bit means is not decided anywhere: nextpnr writes
all four together.  A configuration setting only some of them is reported as
UNDETERMINED, given no identity, and -- because reporting alone would let the
unknown be read as "no conflict" -- refused a verdict by both the model and the
oracle.
"""

from __future__ import annotations

from multiprocessing import Pool
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import exhaustive  # noqa: E402
from exhaustive import (  # noqa: E402
    GlobalDriverGraph,
    ipconfig_bit,
    spi_cells,
    spi_enable_bits,
    spi_fabric_endpoints,
    tile_model,
)
from iceutil import load_icebox, signed_tile_bits  # noqa: E402
import oracle  # noqa: E402
from oracle import conflicting_nets, driver_identity  # noqa: E402

ASC = Path(sys.argv[1] if len(sys.argv) > 1 else "build/spi.asc")
LEDS_ASC = ASC.with_name("leds.asc")
OSC_ASC = ASC.with_name("osc.asc")

LEFT = (0, 0, 0)
RIGHT = (25, 0, 1)
# The class below is 601 whole-graph rebuilds; one worker per core keeps it
# to about two minutes.  Same knob as the oracle sweeps.
WORKERS = max(1, int(os.environ.get("ORACLE_WORKERS", "16")))

# Three named positives.  Two are an SPI output meeting a LUT output, one per
# instance.  The third is two outputs of the *same* instance meeting each
# other: it is a conflict only because each port carries its own identity, so
# it is what a per-instance identity would miss, and the granularity is given
# its own counterfactual below.
POSITIVES = (
    ("left", 0, 19, "B6[51]", "slf_op_3", "sp12_v_b_6",
     ("spi", 0, 0, "SBDATO2"), ("lutff", 12, 1, 1, "out")),
    ("right", 25, 19, "B3[48]", "slf_op_1", "sp4_v_b_18",
     ("spi", 25, 0, "SBDATO0"), ("lutff", 12, 1, 3, "out")),
    ("port-to-port", 0, 19, "B3[53]", "slf_op_1", "sp4_r_v_b_35",
     ("spi", 0, 0, "SBDATO0"), ("spi", 0, 0, "MCSNOE1")),
)

failures: list[str] = []

_ICEBOX = None
_IC = None


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def load(path: Path):
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(path))
    return icebox, ic


def raises(action) -> tuple[bool, str]:
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


def set_ipconfig_bit(ic, x, y, name, value) -> None:
    for entry in ic.tile_db(x, y):
        if entry[1] == "IpConfig" and len(entry) > 2 and entry[2] == name:
            row, column = entry[0][0][1:].rstrip("]").split("[")
            set_bit(ic, x, y, f"B{row}[{column}]", value)
            return
    raise KeyError(f"no IpConfig bit {name} in tile ({x},{y})")


def flip_delta(ic, x, y, bit_name):
    """The routing entries one flip of `bit_name` adds and removes."""
    entries, _muxes, bit_to_entries = tile_model(ic, x, y)
    bits = signed_tile_bits(ic.tile(x, y))
    changed = set(bits)
    if bit_name in bits:
        changed.discard(bit_name)
        changed.add(f"!{bit_name}")
    else:
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


def structural_candidates(ic, endpoints):
    """Every single-bit flip in the SPI tiles that moves one of its routes.

    Enumerated from the database alone, with no reference to any verdict.  The
    point is to be able to check both directions: filtering by "the model says
    conflict" first would leave the model's own negatives unexamined, which is
    the shape of every false-negative this project has had.
    """
    candidates = []
    for x, y in sorted({(sx, sy) for sx, sy, _n in endpoints}):
        _entries, _muxes, bit_to_entries = tile_model(ic, x, y)
        tile = ic.tile(x, y)
        for row, line in enumerate(tile):
            for column, _value in enumerate(line):
                bit_name = f"B{row}[{column}]"
                if bit_name not in bit_to_entries:
                    continue
                additions, removals = flip_delta(ic, x, y, bit_name)
                if not additions and not removals:
                    continue
                if not any(
                    (x, y, entry[2]) in endpoints or (x, y, entry[3]) in endpoints
                    for entry in additions + removals
                ):
                    continue
                candidates.append((x, y, row, column, bit_name, additions, removals))
    return candidates


def _worker_setup(asc: str) -> None:
    global _ICEBOX, _IC
    _ICEBOX = load_icebox()
    _IC = _ICEBOX.iceconfig()
    _IC.read_file(asc)


def _worker_delta(task):
    """Rebuild the whole graph with one bit flipped and count conflicts."""
    x, y, row, column = task
    tile = _IC.tile(x, y)
    original = tile[row]
    flipped = "0" if original[column] == "1" else "1"
    tile[row] = original[:column] + flipped + original[column + 1 :]
    try:
        return oracle.conflicting_nets(_IC, _ICEBOX)
    finally:
        tile[row] = original


def main() -> int:
    icebox, ic = load(ASC)
    cells = dict(spi_cells(icebox))

    print("=== both instances are enabled (read from configuration) ===")
    check(
        "the database knows two SB_SPI instances",
        sorted(cells) == [LEFT, RIGHT],
        f"{sorted(cells)}",
    )
    _leds_icebox, ic_leds = load(LEDS_ASC)
    for placement in (LEFT, RIGHT):
        bits = spi_enable_bits(cells[placement])
        check(
            f"{placement}: four enable bits, as the database states",
            len(bits) == 4,
            f"{bits}",
        )
        values = [ipconfig_bit(ic, x, y, name) for x, y, name in bits]
        check(
            f"{placement}: the fixture writes the full vector",
            values == ["1"] * 4,
            f"read {''.join(str(value) for value in values)}",
        )
        # Without the negative control this passes on bits that are always set.
        cleared = [ipconfig_bit(ic_leds, x, y, name) for x, y, name in bits]
        check(
            f"{placement}: and a design without the IP reads all-clear",
            cleared == ["0"] * 4,
            f"read {''.join(str(value) for value in cleared)}",
        )
        check(
            f"{placement}: every enable bit is in an IO tile, outside every sweep",
            all((x, y) in ic.io_tiles for x, y, _n in bits),
            "the sweeps flip logic tiles only, so no sweep can reach them",
        )
    check(
        "the two instances split their four bits differently",
        {(x, y) for x, y, _n in spi_enable_bits(cells[LEFT])}
        != {(x, y) for x, y, _n in spi_enable_bits(cells[RIGHT])},
        f"left {sorted({(x, y) for x, y, _n in spi_enable_bits(cells[LEFT])})}, "
        f"right {sorted({(x, y) for x, y, _n in spi_enable_bits(cells[RIGHT])})}",
    )

    graph = GlobalDriverGraph(ic, icebox)
    sources = graph.spi_sources
    expected = {
        segment: ("spi", placement[0], placement[1], port)
        for placement, cell in cells.items()
        for segment, port in spi_fabric_endpoints(cell).items()
    }
    print(f"\n  SPI source endpoints: {len(sources)}")
    for placement, cell in sorted(cells.items()):
        check(
            f"{placement}: the database states twenty-five fabric endpoints",
            len(spi_fabric_endpoints(cell)) == 25,
            f"{len(spi_fabric_endpoints(cell))}",
        )
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
        "fifty endpoints, fifty distinct port identities",
        len(sources) == 50 and len(set(sources.values())) == 50,
        f"{len(sources)} endpoints, {len(set(sources.values()))} identities",
    )
    present = {
        segment
        for group in ic.group_segments()
        for segment in group
        if "slf_op" in segment[2]
    }
    check(
        "all fifty appear in the design's own segment graph",
        not (expected.keys() - present),
        f"{sorted(expected.keys() - present)[:3]} missing of {len(present)} present",
    )
    check(
        "no instance is in an undetermined enable state",
        not graph.spi_undetermined,
        f"{graph.spi_undetermined}",
    )
    check(
        "the independent oracle derives the same annotation",
        oracle.spi_driver_state(ic, icebox) == sources,
        "two derivations from the cell database, neither importing the other",
    )
    check("model baseline has no multi-driver net", graph.base_multi_driver_nets == 0)
    check("oracle baseline has no conflicting net", conflicting_nets(ic, icebox) == 0)

    print("\n=== ownership is by endpoint, never by tile ===")
    # (0,19) hosts slf_op_1..7 of the left instance but not slf_op_0, which is
    # no SPI port at all.  A tile-level rule would hand it to the block anyway.
    check(
        "slf_op_0 of tile (0,19) is not an SPI port and is not claimed",
        (0, 19, "slf_op_0") not in sources and (0, 19, "slf_op_1") in sources,
    )
    check(
        "and it resolves to no driver at all",
        driver_identity(ic, icebox, (0, 19, "slf_op_0")) is None,
    )
    entries_with_endpoint_source = sum(
        1
        for x, y in sorted({(sx, sy) for sx, sy, _n in sources})
        for entry in ic.tile_db(x, y)
        if entry[1] in ("routing", "buffer") and (x, y, entry[2]) in sources
    )
    entries_with_endpoint_destination = sum(
        1
        for x, y in sorted({(sx, sy) for sx, sy, _n in sources})
        for entry in ic.tile_db(x, y)
        if entry[1] in ("routing", "buffer") and (x, y, entry[3]) in sources
    )
    check(
        "an SPI endpoint is only ever a routing source, never a destination",
        entries_with_endpoint_source == 648
        and entries_with_endpoint_destination == 0,
        f"{entries_with_endpoint_source} as source, "
        f"{entries_with_endpoint_destination} as destination",
    )

    print("\n=== the overlap guard has to be able to fire ===")
    icebox_g, ic_g = load(OSC_ASC)
    built, _message = raises(lambda: GlobalDriverGraph(ic_g, icebox_g))
    check(
        "the oscillator fixture builds cleanly on its own",
        not built,
        "so the failure below is caused by the injection, not by the fixture",
    )
    original_spi_state = exhaustive.spi_driver_state
    contested = (25, 29, "slf_op_0")

    def with_overlapping_claim(ic_arg, icebox_arg=None):
        state = original_spi_state(ic_arg, icebox_arg)
        state[contested] = ("spi", 25, 0, "INJECTED")
        return state

    exhaustive.spi_driver_state = with_overlapping_claim
    try:
        icebox_o, ic_o = load(OSC_ASC)
        fired, message = raises(lambda: GlobalDriverGraph(ic_o, icebox_o))
    finally:
        exhaustive.spi_driver_state = original_spi_state
    check(
        "an SPI claim on the LFOSC's fabric output is refused, not silently won",
        fired and "slf_op_0" in message,
        message or "no RuntimeError raised",
    )

    # --- known positives ------------------------------------------------------
    for label, x, y, bit_name, source, destination, identity, partner in POSITIVES:
        icebox_p, ic_p = load(ASC)
        graph_p = GlobalDriverGraph(ic_p, icebox_p)
        additions, removals = flip_delta(ic_p, x, y, bit_name)
        model_hit, drivers = graph_p.mutation_creates_multi_driver(
            x, y, additions, removals
        )
        base = conflicting_nets(ic_p, icebox_p)
        set_bit(ic_p, x, y, bit_name, "1")
        after = conflicting_nets(ic_p, icebox_p)
        identities = {driver_identity(ic_p, icebox_p, segment) for segment in drivers}
        print(f"\nSPI positive ({label}): tile=({x},{y}) bit={bit_name}")
        for entry in additions:
            print(f"  add: {entry[2]} -> {entry[3]}")
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
            f"{label}: both expected sources participate",
            {identity, partner} <= identities,
            f"{sorted(i for i in identities if i)}",
        )

    # --- what the per-port granularity is worth ------------------------------
    print("\n=== per-port identities, not per-instance ===")
    label, x, y, bit_name, source, _destination, _identity, _partner = POSITIVES[2]
    icebox_p, ic_p = load(ASC)
    additions, removals = flip_delta(ic_p, x, y, bit_name)

    def per_instance_identity(ic_arg, icebox_arg=None):
        state = original_spi_state(ic_arg, icebox_arg)
        return {
            segment: identity[:3] + ("INSTANCE",)
            for segment, identity in state.items()
        }

    exhaustive.spi_driver_state = per_instance_identity
    try:
        icebox_c, ic_c = load(ASC)
        graph_c = GlobalDriverGraph(ic_c, icebox_c)
        collapsed_hit, _drivers = graph_c.mutation_creates_multi_driver(
            x, y, additions, removals
        )
    finally:
        exhaustive.spi_driver_state = original_spi_state
    check(
        "collapsing the ports to one identity per instance loses that conflict",
        not collapsed_hit and len(set(graph_c.spi_sources.values())) == 2,
        f"conflict={collapsed_hit}, "
        f"{len(set(graph_c.spi_sources.values()))} identities",
    )

    # --- the counterfactual, actually run ------------------------------------
    print("\n=== withholding one endpoint's identity ===")
    label, x, y, bit_name, source, _destination, identity, _partner = POSITIVES[0]
    icebox_p, ic_p = load(ASC)
    additions, removals = flip_delta(ic_p, x, y, bit_name)

    def without_one_endpoint(ic_arg, icebox_arg=None):
        state = original_spi_state(ic_arg, icebox_arg)
        state.pop((x, y, source), None)
        return state

    exhaustive.spi_driver_state = without_one_endpoint
    try:
        icebox_cf, ic_cf = load(ASC)
        graph_cf = GlobalDriverGraph(ic_cf, icebox_cf)
        cf_hit, cf_drivers = graph_cf.mutation_creates_multi_driver(
            x, y, additions, removals
        )
    finally:
        exhaustive.spi_driver_state = original_spi_state
    check(
        "withholding just this endpoint makes the same flip look clean",
        graph_cf.driver_identity((x, y, source)) is None and not cf_hit,
        f"identity={graph_cf.driver_identity((x, y, source))}, conflict={cf_hit}, "
        f"drivers={cf_drivers}",
    )
    check(
        "and the other forty-nine endpoints keep their identities",
        len(graph_cf.spi_sources) == 49,
        f"{len(graph_cf.spi_sources)} left",
    )

    # --- the whole structural class, both directions -------------------------
    print("\n=== every flip that moves an SPI route, model against oracle ===")
    icebox_s, ic_s = load(ASC)
    graph_s = GlobalDriverGraph(ic_s, icebox_s)
    candidates = structural_candidates(ic_s, set(graph_s.spi_sources))
    check(
        "the structural class is 601 flips",
        len(candidates) == 601,
        f"{len(candidates)}",
    )
    shapes = {"adds only": 0, "removals only": 0, "both": 0}
    model_hits = []
    for x, y, _row, _column, _bit, additions, removals in candidates:
        if additions and removals:
            shapes["both"] += 1
        elif additions:
            shapes["adds only"] += 1
        else:
            shapes["removals only"] += 1
        hit, _drivers = graph_s.mutation_creates_multi_driver(x, y, additions, removals)
        model_hits.append(hit)
    check(
        "and it contains removals and an add+remove case, not just additions",
        shapes == {"adds only": 550, "removals only": 50, "both": 1},
        f"{shapes}",
    )
    base = conflicting_nets(ic_s, icebox_s)
    with Pool(
        WORKERS, initializer=_worker_setup, initargs=(str(ASC),)
    ) as pool:
        counts = pool.map(
            _worker_delta,
            [(x, y, row, column) for x, y, row, column, _b, _a, _r in candidates],
            chunksize=4,
        )
    deltas = [count - base for count in counts]
    disagreements = [
        (candidate[0], candidate[1], candidate[4], hit, delta)
        for candidate, hit, delta in zip(candidates, model_hits, deltas)
        if hit != (delta > 0)
    ]
    check(
        "the whole-graph oracle agrees on every one of them, both directions",
        not disagreements,
        f"{disagreements[:3]}",
    )
    check(
        "fifty are conflicts and each is exactly +1",
        sum(model_hits) == 50
        and sorted({delta for delta in deltas}) == [0, 1]
        and sum(1 for delta in deltas if delta == 1) == 50,
        f"{sum(model_hits)} model positives, deltas {sorted(set(deltas))}",
    )
    check(
        "all three named positives are members of the class",
        {(entry[1], entry[2], entry[3]) for entry in POSITIVES}
        <= {(x, y, bit) for x, y, _r, _c, bit, _a, _rm in candidates},
    )

    # --- negative regressions -------------------------------------------------
    print("\n=== negative regressions ===")
    check(
        "a design without hard IP gets no SPI identity",
        not exhaustive.spi_driver_state(ic_leds, icebox),
    )
    check(
        "and has no slf_op segment at all",
        not any(
            "slf_op" in segment[2]
            for group in ic_leds.group_segments()
            for segment in group
        ),
    )
    check(
        "the I2C fixture gets no SPI identity either",
        not exhaustive.spi_driver_state(load(ASC.with_name("i2c.asc"))[1], icebox),
        "and its thirty I2C endpoints are on different tiles entirely",
    )

    icebox_off, ic_off = load(ASC)
    for x_bit, y_bit, name in spi_enable_bits(cells[LEFT]):
        set_ipconfig_bit(ic_off, x_bit, y_bit, name, "0")
    off_sources = exhaustive.spi_driver_state(ic_off, icebox_off)
    check(
        "clearing all four of an instance's enable bits removes its identities",
        not any(identity[1:3] == LEFT[:2] for identity in off_sources.values()),
    )
    check(
        "the other instance is untouched",
        len(off_sources) == 25
        and all(identity[1:3] == RIGHT[:2] for identity in off_sources.values()),
        f"{len(off_sources)} endpoints left",
    )
    check(
        "a disabled instance's slf_op resolves to None",
        driver_identity(ic_off, icebox_off, (0, 19, "slf_op_1")) is None,
    )
    check(
        "and a disabled instance is not reported as undetermined",
        not exhaustive.spi_undetermined(ic_off, icebox_off),
        "all four clear is a determined answer: off",
    )

    for cleared in (1, 2, 3):
        icebox_mixed, ic_mixed = load(ASC)
        for x_bit, y_bit, name in spi_enable_bits(cells[LEFT])[:cleared]:
            set_ipconfig_bit(ic_mixed, x_bit, y_bit, name, "0")
        mixed_sources = exhaustive.spi_driver_state(ic_mixed, icebox_mixed)
        check(
            f"clearing {cleared} of the four bits is reported as undetermined",
            exhaustive.spi_undetermined(ic_mixed, icebox_mixed) == [LEFT]
            and oracle.spi_undetermined(ic_mixed, icebox_mixed) == [LEFT],
            f"model {exhaustive.spi_undetermined(ic_mixed, icebox_mixed)}, "
            f"oracle {oracle.spi_undetermined(ic_mixed, icebox_mixed)}",
        )
        check(
            f"clearing {cleared}: no identity is given either way",
            not any(identity[1:3] == LEFT[:2] for identity in mixed_sources.values())
            and len(mixed_sources) == 25,
            "claiming it drives would invent twenty-five drivers; claiming it "
            "does not would hide them",
        )
        fired, message = raises(lambda: GlobalDriverGraph(ic_mixed, icebox_mixed))
        check(
            f"clearing {cleared}: the model refuses to build a verdict",
            fired and str(LEFT) in message,
            message or "the graph was built and reported a baseline anyway",
        )
        fired, message = raises(lambda: conflicting_nets(ic_mixed, icebox_mixed))
        check(
            f"clearing {cleared}: the oracle refuses to count conflicts",
            fired and str(LEFT) in message,
            message or "the oracle returned a count anyway",
        )
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
    print("PASS: SPI fixture, three named positives, the whole structural class, "
          "and every negative regression")
    print(
        "Coverage boundary: the twenty-five fabric outputs of each of the two "
        "SB_SPI instances, gated on the enable bits the cell database names.  "
        "The block's inputs, its register semantics, and what any single "
        "enable bit means on its own are outside it.  LEDDA is surveyed but "
        "its enable state is not a configuration fact, and SB_RGBA_DRV has no "
        "fabric-facing output and is not applicable to the driver graph."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

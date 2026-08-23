#!/usr/bin/env python3
"""Guard the enumeration that two defects in this project came from.

Both defects produced a clean-looking negative from an incomplete list:

  * the global driver check was gated on a local condition and never saw the
    cross-tile class;
  * a diff enumerated io, logic, ipcon, ramb and ramt tiles and concluded that
    `CLKHF_DIV` left no trace in the ASC, when it is encoded in `dsp_tiles`.

The lesson is that "no difference" is only evidence once the enumeration is
shown to be complete.  This script enforces that:

  1. every tile collection an `iceconfig` actually exposes is either iterated by
     `iceutil.configuration_tiles` or named in `NON_TILE_CONFIGURATION` with a
     reason -- a new collection in a future icebox fails here rather than being
     skipped in silence;
  2. the canonical iterator demonstrably reaches `dsp_tiles`;
  3. the specific regression: a diff built on the canonical iterator finds the
     CLKHF_DIV bit, and the old hand-written list does not.  The second half is
     kept deliberately -- it is the failing case, and a guard whose failing case
     is not exercised proves nothing.
"""

from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from iceutil import (  # noqa: E402
    NON_TILE_CONFIGURATION,
    TILE_COLLECTIONS,
    assert_tile_coverage,
    configuration_tiles,
    load_icebox,
)

FIXTURES = ("leds.asc", "dense.asc", "pll.asc", "spram.asc", "osc.asc")

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


def differing_tiles(left, right, collections):
    """Coordinates that differ, enumerated over the given collection names."""
    found = []
    for name in collections:
        left_value = getattr(left, name)
        right_value = getattr(right, name)
        pairs = (
            zip(left_value, right_value)
            if isinstance(left_value, list)
            else [(left_value, right_value)]
        )
        for index, (left_map, right_map) in enumerate(pairs):
            for coordinate, tile in left_map.items():
                other = right_map.get(coordinate)
                if other is None or tile == other:
                    continue
                for row in range(len(tile)):
                    for column in range(len(tile[row])):
                        if tile[row][column] != other[row][column]:
                            found.append((name, index, coordinate, row, column))
    return found


def main() -> int:
    print("=== 1. every tile collection is classified ===")
    for fixture in FIXTURES:
        path = ROOT / "build" / fixture
        if not path.exists():
            check(f"{fixture} present", False, "run `make all` first")
            continue
        _icebox, ic = load(path)
        try:
            assert_tile_coverage(ic)
            check(f"{fixture}: no unclassified tile collection", True)
        except AssertionError as error:
            check(f"{fixture}: no unclassified tile collection", False, str(error))
    print(f"  iterated: {', '.join(TILE_COLLECTIONS)}")
    print(f"  named as non-tile configuration: {', '.join(sorted(NON_TILE_CONFIGURATION))}")

    print("\n=== 2. the iterator actually reaches dsp_tiles ===")
    _icebox, ic = load(ROOT / "build" / "leds.asc")
    visited = {name for name, _coordinate, _tile in configuration_tiles(ic)}
    check(
        "dsp_tiles are visited",
        any(name.startswith("dsp_tiles") for name in visited),
        f"{sorted(visited)}",
    )

    print("\n=== 3. regression: the CLKHF_DIV bit is found, and was missed before ===")
    import osc_evidence  # noqa: PLC0415

    ascs = {}
    for value in ("0b00", "0b10"):
        name = f"hfosc_div{value[2:]}"
        path = osc_evidence.BUILD / f"{name}.asc"
        if not path.exists():
            path = osc_evidence.build(name, osc_evidence.HFOSC_ONLY, osc_evidence.PCF_LEDS, div=value)
        ascs[value] = load(path)[1]

    canonical = differing_tiles(ascs["0b00"], ascs["0b10"], TILE_COLLECTIONS)
    print(f"  canonical enumeration finds: {canonical}")
    check(
        "the canonical enumeration finds the divider bit",
        len(canonical) == 1
        and canonical[0][0] == "dsp_tiles"
        and canonical[0][2] == (0, 16),
        f"{canonical}",
    )

    old_list = ("io_tiles", "logic_tiles", "ipcon_tiles", "ramb_tiles", "ramt_tiles")
    missed = differing_tiles(ascs["0b00"], ascs["0b10"], old_list)
    print(f"  the old hand-written list finds: {missed or '(nothing)'}")
    check(
        "the old list misses it, which is why this guard exists",
        not missed,
        "kept as the failing case: a guard whose failure mode is never exercised "
        "proves nothing",
    )

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: tile enumeration is complete, and the regression that motivated it holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

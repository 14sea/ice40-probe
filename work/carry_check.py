#!/usr/bin/env python3
"""Regressions for the carry-out driver identity.

`lutff_N/cout` is a second physical output of a logic cell, and it was missing
from the source ontology: the driver pattern matched only `out` and `lout`.  An
exhaustive "which components have no driver at all" check over the RGBA fixture
surfaced 22 such components, every one of them a carry pair.

Two things make this more than a spelling fix.

First, the identity must be gated.  `lutff_N/cout -> lutff_{N+1}/in_3` is a
programmable routing entry, not a hardwired link, so a mutation can pull the
`cout` segment into the graph inside a cell whose carry logic is switched off.
Calling that a source would invent a driver that does not exist.  The gate is
CarryEnable, sequential bit 0 of the cell.  `tile (1,4) LC0` in the leds fixture
is such a cell and is used as the negative case below.

Second, and more usefully: adding the identity changes no result, and that is
provable rather than lucky.  Across all 660 logic tiles, `cout` appears as a
routing source only ever with `in_3` as its destination, and never as a
destination itself; and `in_3`'s mux carries all sixteen of its sources on a
single bit group, so they are mutually exclusive.  A net containing `cout`
therefore cannot also contain another source.  That is why this script pins the
structural argument instead of a named multi-source case: such a case is not
merely absent from these fixtures, it cannot be constructed.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from exhaustive import GlobalDriverGraph, analyse, tile_model  # noqa: E402
from iceutil import configuration_tiles, load_icebox, signed_tile_bits  # noqa: E402

COUT = re.compile(r"lutff_([0-7])/cout").fullmatch
IN_3 = re.compile(r"lutff_[0-7]/in_3").fullmatch

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def load(name: str):
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(ROOT / "build" / name))
    return icebox, ic


def main() -> int:
    icebox, ic = load("leds.asc")
    graph = GlobalDriverGraph(ic, icebox)

    print("=== the identity is recognised where carry is enabled ===")
    recognised = []
    for group in ic.group_segments():
        for segment in group:
            match = COUT(segment[2])
            if not match:
                continue
            identity = graph.driver_identity(segment)
            if identity is not None:
                recognised.append((segment, identity))
    print(f"  carry outputs in the graph with an identity: {len(recognised)}")
    if recognised:
        print(f"  example: {recognised[0][0]} -> {recognised[0][1]}")
    check("every enabled carry output is a source", len(recognised) == 24,
          f"{len(recognised)} of 24 expected in the leds fixture")
    check(
        "the identity is distinct from the cell's LUT output",
        all(identity[4] == "carry" for _segment, identity in recognised),
        "an LC's carry out and its LUT out are two different physical outputs",
    )

    print("\n=== and withheld where carry is disabled ===")
    x, y, index = 1, 4, 0
    tile = ic.logic_tiles[(x, y)]
    carry_enable = icebox.get_lutff_seq_bits(tile, index)[0]
    check(f"tile ({x},{y}) LC{index} has CarryEnable={carry_enable}", carry_enable == "0")
    entries, _muxes, bit_to_entries = tile_model(ic, x, y)
    entry = next(
        e for e in entries if e[2] == f"lutff_{index}/cout" and IN_3(str(e[3]))
    )
    bits = signed_tile_bits(tile)
    check(
        "its cout -> in_3 entry exists and is currently disabled",
        not all(bit in bits for bit in entry[0]),
        f"{entry[2]} -> {entry[3]}",
    )
    for bit in entry[0]:
        if bit.startswith("!"):
            continue
        row, column = bit[1:].rstrip("]").split("[")
        row, column = int(row), int(column)
        tile[row] = tile[row][:column] + "1" + tile[row][column + 1 :]
    mutated = GlobalDriverGraph(ic, icebox)
    segment = (x, y, f"lutff_{index}/cout")
    present = any(segment in group for group in ic.group_segments())
    check("enabling it pulls the cout segment into the graph", present)
    check(
        "but it is still not a source, because the cell generates no carry",
        mutated.driver_identity(segment) is None,
        "an ungated regex would invent a driver here",
    )

    print("\n=== why no multi-source case involving carry can exist ===")
    # Exact counts, over every logic tile and every in_3 mux.  Spot-checking one
    # mux would leave the argument resting on the assumption that the rest look
    # the same -- and an incomplete enumeration producing a clean negative is
    # the failure mode this project has already hit twice.
    _icebox2, clean = load("leds.asc")
    tiles = cout_as_source = cout_as_destination = cout_to_other = 0
    in_3_as_source = 0
    cout_entries_per_tile = Counter()
    in_3_muxes = wrong_source_count = inconsistent_bit_group = 0
    jointly_satisfiable = 0
    for _collection, (tile_x, tile_y), _tile in configuration_tiles(clean):
        if (tile_x, tile_y) not in clean.logic_tiles:
            continue
        tiles += 1
        here = 0
        for candidate in clean.tile_db(tile_x, tile_y):
            if candidate[1] not in ("routing", "buffer"):
                continue
            if COUT(str(candidate[2])):
                cout_as_source += 1
                here += 1
                if not IN_3(str(candidate[3])):
                    cout_to_other += 1
            if COUT(str(candidate[3])):
                cout_as_destination += 1
            if IN_3(str(candidate[2])):
                in_3_as_source += 1
        cout_entries_per_tile[here] += 1

        _entries, muxes, _bits = tile_model(clean, tile_x, tile_y)
        for destination, group in muxes.items():
            if not IN_3(destination):
                continue
            in_3_muxes += 1
            if len(group) != 16:
                wrong_source_count += 1
            bit_groups = {
                frozenset(name[1:] if name.startswith("!") else name for name in entry[0])
                for entry in group
            }
            if len(bit_groups) != 1:
                inconsistent_bit_group += 1
            for left_index, left in enumerate(group):
                left_polarity = {
                    name[1:] if name.startswith("!") else name: name.startswith("!")
                    for name in left[0]
                }
                for right in group[left_index + 1 :]:
                    right_polarity = {
                        name[1:] if name.startswith("!") else name: name.startswith("!")
                        for name in right[0]
                    }
                    if all(
                        left_polarity[name] == right_polarity[name]
                        for name in left_polarity.keys() & right_polarity.keys()
                    ):
                        jointly_satisfiable += 1

    check("every logic tile was examined", tiles == 660, f"{tiles}")
    check("carry out is a routing source 4,620 times",
          cout_as_source == 4620, f"{cout_as_source}")
    check("uniformly, seven entries in every tile",
          dict(cout_entries_per_tile) == {7: 660}, f"{dict(cout_entries_per_tile)}")
    check("carry out never routes anywhere but in_3",
          cout_to_other == 0, f"{cout_to_other}")
    check("carry out is never a routing destination",
          cout_as_destination == 0, f"{cout_as_destination}")
    check("in_3 is never a routing source",
          in_3_as_source == 0, f"{in_3_as_source}")
    check("every logic tile contributes eight in_3 muxes",
          in_3_muxes == 5280, f"{in_3_muxes}")
    check("each of them carries exactly sixteen sources",
          wrong_source_count == 0, f"{wrong_source_count} mux(es) do not")
    check("each of them decodes on a single bit group",
          inconsistent_bit_group == 0, f"{inconsistent_bit_group} mux(es) do not")
    check("so no two of an in_3 mux's sources can be selected at once",
          jointly_satisfiable == 0, f"{jointly_satisfiable} satisfiable pair(s)")
    print(
        "  => a net containing cout cannot contain a second source, so adding\n"
        "     this identity provably cannot change any sweep result"
    )

    print("\n=== the positive set is recomputed, not quoted ===")
    for fixture, expected, results in (
        ("leds.asc", 14, "oracle_leds_full.jsonl"),
        ("dense.asc", 2471, "oracle_dense_full.jsonl"),
    ):
        icebox_here, current = load(fixture)
        result = analyse(current, icebox_here)
        check(f"{fixture} baseline has no multi-driver net",
              result.base_multi_driver_nets == 0)
        # Two independent tallies of the same thing: the running counter, and
        # the set of coordinates.  They can only agree if every positive was
        # visited exactly once.
        counted = result.count("global multi-driver net candidate")
        coordinates = result.global_positives
        check(f"{fixture}: the current model finds {expected} positives",
              counted == expected, f"{counted}")
        check(f"{fixture}: and {expected} distinct coordinates, one visit each",
              len(coordinates) == expected, f"{len(coordinates)}")

        path = ROOT / "results" / results
        if not path.exists():
            print(f"  [skip] {results} not present; run the sweep to compare coordinates")
            continue
        archived = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("record") or not record["oracle"]:
                continue
            archived.add((record["x"], record["y"], record["row"], record["column"]))
        # Both directions.  Counting the archive alone would pass even if the
        # current model had moved every positive somewhere else.
        lost = sorted(archived - coordinates)
        gained = sorted(coordinates - archived)
        check(f"{fixture}: every archived positive is still found",
              not lost, f"{len(lost)} lost: {lost[:3]}")
        check(f"{fixture}: and the model invents none the archive lacks",
              not gained, f"{len(gained)} new: {gained[:3]}")
        check(f"{fixture}: archived positive count is {expected}",
              len(archived) == expected, f"{len(archived)}")

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: carry-out is a gated source, and provably cannot change a verdict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

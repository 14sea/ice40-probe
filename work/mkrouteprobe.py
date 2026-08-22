#!/usr/bin/env python3
"""Build, but never program, a checked single-routing-bit probe.

The requested flip must be an additions-only local dual-route candidate that
also joins two drivers in IceStorm's configured-net graph.  This tool only
creates host-side ASC/BIN/Verilog artifacts; it has no programmer support.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from exhaustive import GlobalDriverGraph, selected, tile_model
from iceutil import COLS, ROWS, load_icebox, signed_tile_bits


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("tile_x", type=int)
    parser.add_argument("tile_y", type=int)
    parser.add_argument("row", type=int, choices=range(ROWS))
    parser.add_argument("column", type=int, choices=range(COLS))
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--source-asc", type=Path, default=Path("work/leds.asc"))
    return parser.parse_args()


def changed_model(ic, x: int, y: int, row: int, column: int):
    entries, muxes, bit_to_entries = tile_model(ic, x, y)
    name = f"B{row}[{column}]"
    touched_indexes = bit_to_entries.get(name, ())
    if not touched_indexes:
        raise ValueError(f"{name} is not a routing coordinate in tile ({x}, {y})")

    bits = signed_tile_bits(ic.logic_tiles[(x, y)])
    was_one = ic.logic_tiles[(x, y)][row][column] == "1"
    changed_bits = set(bits)
    changed_bits.remove(("" if was_one else "!") + name)
    changed_bits.add(("!" if was_one else "") + name)

    additions = []
    removals = []
    for index in touched_indexes:
        entry = entries[index]
        before = all(bit in bits for bit in entry[0])
        after = all(bit in changed_bits for bit in entry[0])
        if after and not before:
            additions.append(entry)
        elif before and not after:
            removals.append(entry)

    destinations = {entries[index][3] for index in touched_indexes}
    dual_routes = []
    for destination in destinations:
        before = selected(muxes[destination], bits)
        after = selected(muxes[destination], changed_bits)
        if len(after) > 1:
            dual_routes.append((destination, before, after))
    return was_one, additions, removals, dual_routes


def flip_asc(
    source: Path, destination: Path, x: int, y: int, row: int, column: int
) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    marker = f".logic_tile {x} {y}"
    try:
        tile_start = lines.index(marker) + 1
    except ValueError as error:
        raise ValueError(f"logic tile not found: ({x}, {y})") from error
    tile = lines[tile_start : tile_start + ROWS]
    if len(tile) != ROWS or any(len(line) != COLS for line in tile):
        raise ValueError(f"malformed logic tile at ({x}, {y})")
    values = list(tile[row])
    values[column] = "0" if values[column] == "1" else "1"
    lines[tile_start + row] = "".join(values)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def decode_asc(source: Path, destination: Path) -> None:
    with destination.open("w", encoding="utf-8") as output:
        subprocess.run(
            ["icebox_vlog", str(source)],
            check=True,
            stdout=output,
            text=True,
        )


def main() -> int:
    args = arguments()
    prefix = args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    asc_path = prefix.with_suffix(".asc")
    bin_path = prefix.with_suffix(".bin")
    vlog_path = prefix.with_suffix(".v")
    if asc_path.resolve() == args.source_asc.resolve():
        raise ValueError("output ASC must not overwrite the source ASC")

    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(args.source_asc))
    if (args.tile_x, args.tile_y) not in ic.logic_tiles:
        raise ValueError(f"logic tile not found: ({args.tile_x}, {args.tile_y})")

    was_one, additions, removals, dual_routes = changed_model(
        ic, args.tile_x, args.tile_y, args.row, args.column
    )
    if not dual_routes:
        raise ValueError("flip is not a local dual-route candidate")
    if not additions or removals:
        raise ValueError("flip is not additions-only")
    driver_graph = GlobalDriverGraph(ic)
    if not driver_graph.addition_creates_multi_driver(
        args.tile_x, args.tile_y, additions
    ):
        raise ValueError("flip does not create an IceStorm global multi-driver candidate")

    flip_asc(
        args.source_asc,
        asc_path,
        args.tile_x,
        args.tile_y,
        args.row,
        args.column,
    )
    subprocess.run(["icepack", str(asc_path), str(bin_path)], check=True)
    decode_asc(asc_path, vlog_path)

    print(
        f"flip: tile=({args.tile_x},{args.tile_y}) "
        f"B{args.row}[{args.column}] {int(was_one)}->{int(not was_one)}"
    )
    for entry in additions:
        source_drivers, destination_drivers = driver_graph.endpoint_drivers(
            args.tile_x, args.tile_y, entry
        )
        print(f"add: {entry[2]} -> {entry[3]}")
        print(f"source drivers: {source_drivers}")
        print(f"destination drivers: {destination_drivers}")
    print("safety: host artifacts only; no FPGA programming was performed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error

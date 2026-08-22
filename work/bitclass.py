#!/usr/bin/env python3
"""Classify UP5K logic-tile coordinates and sample single-bit flips.

The classifications are relative to the installed IceStorm database. They are
not an independent statement about undocumented or reserved silicon features.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import random

from iceutil import (
    COLS,
    ROWS,
    is_lc_seq_position,
    is_lut_init_position,
    load_icebox,
    positive_bit_name,
    signed_tile_bits,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("asc", nargs="?", default="work/leds.asc")
    parser.add_argument("samples", nargs="?", type=int, default=20_000)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=0xB17D)
    return parser.parse_args()


def tile_model(ic, x: int, y: int):
    entries = []
    classes = {}
    bit_to_entries = defaultdict(list)
    muxes = defaultdict(list)
    for entry in ic.tile_db(x, y):
        function = entry[1]
        if function in ("routing", "buffer"):
            if not ic.tile_has_net(x, y, entry[2]) or not ic.tile_has_net(x, y, entry[3]):
                continue
            bit_class = "routing"
        elif function.startswith("LC_"):
            bit_class = "lc"
        else:
            bit_class = "other"

        index = len(entries)
        entries.append(entry)
        if function in ("routing", "buffer"):
            muxes[entry[3]].append(entry)
        for signed_name in entry[0]:
            name = positive_bit_name(signed_name)
            if function in ("routing", "buffer"):
                bit_to_entries[name].append(index)
            if classes.get(name) != "routing":
                classes[name] = bit_class
    return entries, classes, bit_to_entries, muxes


def selected(entries, bits: set[str]):
    return [entry for entry in entries if all(name in bits for name in entry[0])]


def main() -> int:
    args = arguments()
    random.seed(args.seed)
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(args.asc)

    totals = Counter()
    configured_tiles = 0
    models = {}
    for (x, y), tile in sorted(ic.logic_tiles.items()):
        model = tile_model(ic, x, y)
        configured = any("1" in row for row in tile)
        configured_tiles += int(configured)
        models[(x, y)] = (*model, configured, signed_tile_bits(tile))
        classes = model[1]
        for row in range(ROWS):
            for column in range(COLS):
                name = f"B{row}[{column}]"
                bit_class = classes.get(name, "database-unreferenced")
                if bit_class == "lc":
                    if is_lut_init_position(row, column):
                        bit_class = "lut_init"
                    elif is_lc_seq_position(row, column):
                        bit_class = "lc_seq"
                totals[bit_class] += 1

    print("=== IceStorm-relative coordinate census, UP5K logic tiles ===")
    print(f"logic tiles           : {len(ic.logic_tiles)}   ({configured_tiles} non-zero)")
    print(f"coordinates per tile  : {ROWS * COLS}")
    denominator = len(ic.logic_tiles) * ROWS * COLS
    for name, count in totals.most_common():
        print(
            f"  {name:<22} {count:8d}  {100.0 * count / denominator:5.1f}%"
            f"   ({count // len(ic.logic_tiles):3d} /tile)"
        )

    results = Counter()
    keys = sorted(ic.logic_tiles)
    for _ in range(args.samples):
        xy = random.choice(keys)
        entries, classes, bit_to_entries, muxes, configured, bits = models[xy]
        tile = ic.logic_tiles[xy]
        row = random.randrange(ROWS)
        column = random.randrange(COLS)
        name = f"B{row}[{column}]"
        bit_class = classes.get(name, "database-unreferenced")
        if bit_class == "lc":
            bit_class = "lut_init" if is_lut_init_position(row, column) else "lc_seq"
        results[f"class:{bit_class}"] += 1
        results["tile:non-zero" if configured else "tile:all-zero"] += 1

        was_one = tile[row][column] == "1"
        changed_bits = set(bits)
        changed_bits.discard(("" if was_one else "!") + name)
        changed_bits.add(("!" if was_one else "") + name)
        touched = {entries[index][3] for index in bit_to_entries.get(name, ())}
        if any(len(selected(muxes[dst], changed_bits)) > 1 for dst in touched):
            results["effect:local dual-route candidate"] += 1

    print(f"\n=== {args.samples} deterministic random flips over all logic tiles ===")
    for name, count in sorted(results.items()):
        print(f"  {name:<40} {count:7d}  {100.0 * count / args.samples:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

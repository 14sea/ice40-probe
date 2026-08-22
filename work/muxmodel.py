#!/usr/bin/env python3
"""Sample local routing-entry effects of UP5K logic-tile bit flips."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import random

from iceutil import COLS, ROWS, load_icebox, positive_bit_name, signed_tile_bits


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("asc", nargs="?", default="work/leds.asc")
    parser.add_argument("samples", nargs="?", type=int, default=20_000)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=0xB17D)
    return parser.parse_args()


def tile_model(ic, x: int, y: int):
    muxes = defaultdict(list)
    bit_to_destinations = defaultdict(set)
    for entry in ic.tile_db(x, y):
        if entry[1] not in ("routing", "buffer"):
            continue
        if not ic.tile_has_net(x, y, entry[2]) or not ic.tile_has_net(x, y, entry[3]):
            continue
        muxes[entry[3]].append(entry)
        for signed_name in entry[0]:
            bit_to_destinations[positive_bit_name(signed_name)].add(entry[3])
    return muxes, bit_to_destinations


def selected(entries, bits: set[str]):
    return [entry[2] for entry in entries if all(name in bits for name in entry[0])]


def main() -> int:
    args = arguments()
    random.seed(args.seed)
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(args.asc)

    cache = {}
    effects = Counter()
    classes = Counter()
    keys = sorted(ic.logic_tiles)
    for _ in range(args.samples):
        xy = random.choice(keys)
        tile = ic.logic_tiles[xy]
        if xy not in cache:
            cache[xy] = (*tile_model(ic, *xy), signed_tile_bits(tile))
        muxes, bit_to_destinations, bits = cache[xy]
        row = random.randrange(ROWS)
        column = random.randrange(COLS)
        name = f"B{row}[{column}]"
        destinations = bit_to_destinations.get(name, ())
        if not destinations:
            classes["non-routing coordinate"] += 1
            continue
        classes["routing coordinate"] += 1

        was_one = tile[row][column] == "1"
        changed_bits = set(bits)
        changed_bits.discard(("" if was_one else "!") + name)
        changed_bits.add(("!" if was_one else "") + name)
        for destination in destinations:
            before = selected(muxes[destination], bits)
            after = selected(muxes[destination], changed_bits)
            if len(after) > 1:
                effects["local dual-route candidate"] += 1
            elif len(before) == 1 and len(after) == 1 and before != after:
                effects["route source changed"] += 1
            elif len(before) == 0 and len(after) == 1:
                effects["new route entry enabled"] += 1
            elif len(before) == 1 and len(after) == 0:
                effects["route entry disabled"] += 1
            else:
                effects["no local mux change"] += 1

    print(f"=== {args.samples} deterministic random flips ===")
    for name, count in classes.most_common():
        print(f"  {name:<30} {count:7d}")
    endpoint_effects = sum(effects.values())
    print(f"\nendpoint effects: {endpoint_effects}")
    for name, count in effects.most_common():
        print(f"  {name:<30} {count:7d}  {100.0 * count / max(endpoint_effects, 1):5.1f}%")
    print("Counts above describe IceStorm routing-entry structure, not measured silicon behaviour.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

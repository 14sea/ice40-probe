#!/usr/bin/env python3
"""Exhaustively classify single-bit flips in non-zero UP5K logic tiles.

Local mux effects come from the IceStorm tile database. Potential multi-driver
nets are additionally checked against IceStorm's full enabled-segment graph.
They remain model predictions, not electrical measurements on silicon.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import re

from iceutil import (
    COLS,
    ROWS,
    is_lut_init_position,
    load_icebox,
    positive_bit_name,
    signed_tile_bits,
)


LUT_DRIVER = re.compile(r"lutff_([0-7])/(out|lout)").fullmatch
IO_DRIVER = re.compile(r"io_([01])/D_IN_([01])").fullmatch
RAM_DRIVER = re.compile(r"ram/RDATA_\d+").fullmatch
DSP_DRIVER = re.compile(r"mult/O_\d+").fullmatch
PLL_CONFIG_BIT = re.compile(r"B(\d+)\[(\d+)\]").fullmatch


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("asc", nargs="?", default="work/leds.asc")
    parser.add_argument(
        "--details",
        action="store_true",
        help="list every global or local multi-driver candidate and its endpoints",
    )
    return parser.parse_args()


def selected(entries, bits: set[str]):
    return [entry for entry in entries if all(name in bits for name in entry[0])]


def pll_driver_state(ic, icebox):
    """Decode active PLL output sources from configuration, not net names.

    IceStorm exposes a PLL output through the IO tile occupied by that output.
    Its global path is represented separately by a ``padin_glb_netwk`` extra
    bit.  Return both the configured source annotation for those graph
    endpoints and the occupied IO blocks whose ordinary input identity must be
    suppressed.
    """
    bit_indices = {}
    for entry in icebox.iotile_l_db:
        if entry[1] != "PLL":
            continue
        match = PLL_CONFIG_BIT(entry[0][0])
        if match:
            bit_indices[entry[2]] = (int(match.group(1)), int(match.group(2)))

    enabled_globals = set()
    for bit in ic.extra_bits:
        entry = ic.lookup_extra_bit(bit)
        if entry[0] == "padin_glb_netwk":
            enabled_globals.add(int(entry[1]))
    global_for_pio = {pio: index for index, pio in enumerate(ic.padin_pio_db())}

    sources = {}
    occupied = {}
    for pll_id in ic.pll_list():
        info = icebox.pllinfo_db[pll_id]

        def config_bit(name):
            x, y, bit_name = info[name]
            row, column = bit_indices[bit_name]
            return ic.tile(x, y)[row][column]

        pll_type = "".join(config_bit(f"PLLTYPE_{index}") for index in (2, 1, 0))
        if pll_type == "000":
            continue

        ports = ("A",) if pll_type in ("010", "011") else ("A", "B")
        pll_x, pll_y = info["LOC"]
        for port in ports:
            pio = info[f"PLLOUT_{port}"]
            x, y, block = pio
            identity = ("pll", pll_x, pll_y, port)
            occupied[(x, y, block)] = identity
            sources[(x, y, f"io_{block}/D_IN_0")] = identity
            global_index = global_for_pio.get(pio)
            if global_index in enabled_globals:
                # glb_netwk_* remains passive; this annotation represents the
                # configured PLL source feeding the distribution network.
                sources[(x, y, f"glb_netwk_{global_index}")] = identity
    return sources, occupied


def ipconfig_bit(ic, x, y, name):
    """Read one named IpConfig bit out of an ipcon tile."""
    for entry in ic.tile_db(x, y):
        if entry[1] == "IpConfig" and len(entry) > 2 and entry[2] == name:
            row, column = entry[0][0][1:].rstrip("]").split("[")
            return ic.tile(x, y)[int(row)][int(column)]
    return None


def spram_driver_state(ic):
    """Decode active SPRAM read-data sources from configuration.

    UP5K single-port RAM is hard IP in the ipcon columns.  Its read data leaves
    the IP through `slf_op_*` segments on ipcon tiles -- a name that appears
    nowhere in a design without hard IP -- so a whitelist built around
    `lutff_*/out`, `io_*/D_IN_*`, `ram/RDATA_*` and `mult/O_*` never sees it and
    the entire read port looks like an undriven net.

    Layout, measured by placing one and then four SB_SPRAM256KA instances: each
    ipcon column carries two instances; `CBIT_0` in that column's row-1 tile
    enables the instance whose 16 outputs occupy rows 1 and 2, and `CBIT_1`
    enables the one occupying rows 3 and 4.  Every output bit is its own
    physical driver, so each segment gets its own identity.
    """
    sources = {}
    if not ic.ipcon_tiles:
        return sources
    for x in sorted({tile_x for tile_x, _ in ic.ipcon_tiles}):
        if (x, 1) not in ic.ipcon_tiles:
            continue
        for cbit, rows in ((0, (1, 2)), (1, (3, 4))):
            if ipconfig_bit(ic, x, 1, f"CBIT_{cbit}") != "1":
                continue
            for y in rows:
                if (x, y) not in ic.ipcon_tiles:
                    continue
                for index in range(8):
                    sources[(x, y, f"slf_op_{index}")] = ("spram", x, y, index)
    return sources


# padin index -> on-chip oscillator, established by placing each oscillator
# alone: HFOSC alone sets padin_glb_netwk 4, LFOSC alone sets 5.
OSCILLATOR_PADIN = {4: "hfosc", 5: "lfosc"}


def oscillator_driver_state(ic, pll_sources):
    """Annotate the global networks driven by the on-chip oscillators.

    An oscillator, like a PLL global output, reaches `glb_netwk_*` with no
    source segment of its own, so the whole network is otherwise driverless.

    The pad-versus-hard-IP ambiguity is resolved by measurement, not assumption:
    driving a global from the very package pin that shares padin index 4 sets no
    extra bit at all and puts the pad's own `io_0/D_IN_0` in the component, so a
    `padin_glb_netwk` extra bit means the source is on-chip.  Only the two
    indices with evidence are annotated; any other index is left alone.
    """
    sources = {}
    padin = ic.padin_pio_db()
    for bit in ic.extra_bits:
        entry = ic.lookup_extra_bit(bit)
        if entry[0] != "padin_glb_netwk":
            continue
        index = int(entry[1])
        kind = OSCILLATOR_PADIN.get(index)
        if kind is None or index >= len(padin):
            continue
        x, y, _block = padin[index]
        segment = (x, y, f"glb_netwk_{index}")
        if segment in pll_sources:
            # An enabled PLL already owns this network; do not add a second
            # identity for one physical source.
            continue
        sources[segment] = (kind, x, y)
    return sources


class GlobalDriverGraph:
    """Split-aware configured-net graph for evaluating routing mutations.

    IceStorm's fixed neighbour/span expansion is first contracted into static
    components.  Enabled database routing/buffer entries are then represented
    as counted edges between those components.  A mutation can therefore add
    and remove programmable edges without pretending that union-find supports
    deletion.
    """

    def __init__(self, ic, icebox=None):
        if icebox is None:
            icebox = load_icebox()
        self.ic = ic
        self.icebox = icebox
        self.pll_sources, self.pll_output_blocks = pll_driver_state(ic, icebox)
        self.spram_sources = spram_driver_state(ic)
        self.oscillator_sources = oscillator_driver_state(ic, self.pll_sources)
        seeds = set()
        enabled_edges = []
        tile_collections = (
            ic.io_tiles,
            ic.logic_tiles,
            ic.ramb_tiles,
            ic.ramt_tiles,
            *ic.dsp_tiles,
            ic.ipcon_tiles,
        )
        for tiles in tile_collections:
            for (x, y), tile in tiles.items():
                config = icebox.tileconfig(tile)
                for entry in ic.tile_db(x, y):
                    if entry[1] not in ("routing", "buffer"):
                        continue
                    if not ic.tile_has_net(x, y, entry[2]) or not ic.tile_has_net(
                        x, y, entry[3]
                    ):
                        continue
                    left = (x, y, entry[2])
                    right = (x, y, entry[3])
                    seeds.update((left, right))
                    if config.match(entry[0]):
                        enabled_edges.append((left, right))
        seeds.update(self.pll_sources)

        # Seed every possible programmable endpoint but suppress all
        # programmable matches.  group_segments() then returns only IceStorm's
        # fixed span/neighbour/global connectivity.
        original_match = icebox.tileconfig.match
        try:
            icebox.tileconfig.match = lambda _self, _bits: False
            static_components = list(ic.group_segments(extra_segments=list(seeds)))
        finally:
            icebox.tileconfig.match = original_match

        self.segment_to_static = {
            segment: index
            for index, segments in enumerate(static_components)
            for segment in segments
        }
        missing = seeds - self.segment_to_static.keys()
        if missing:
            raise RuntimeError(f"IceStorm omitted {len(missing)} routing endpoints")

        self.static_drivers = defaultdict(dict)
        for index, segments in enumerate(static_components):
            for segment in segments:
                identity = self.driver_identity(segment)
                if identity is not None:
                    self.static_drivers[index].setdefault(identity, segment)

        self.edge_counts = Counter()
        self.adjacency = defaultdict(set)
        for left, right in enabled_edges:
            edge = self.edge_for_segments(left, right)
            if edge is None:
                continue
            self.edge_counts[edge] += 1
            self.adjacency[edge[0]].add(edge[1])
            self.adjacency[edge[1]].add(edge[0])

        parents = list(range(len(static_components)))

        def root(component: int) -> int:
            while parents[component] != component:
                parents[component] = parents[parents[component]]
                component = parents[component]
            return component

        for left, right in self.edge_counts:
            left = root(left)
            right = root(right)
            if left != right:
                parents[right] = left
        self.base_component = [root(index) for index in range(len(parents))]
        full_component_for_root = {}
        for full_index, segments in enumerate(ic.group_segments()):
            reconstructed = {
                self.component_for(segment)
                for segment in segments
            }
            if len(reconstructed) != 1:
                raise RuntimeError(
                    "split-aware graph does not reproduce an IceStorm base component"
                )
            reconstructed_root = reconstructed.pop()
            previous = full_component_for_root.setdefault(
                reconstructed_root, full_index
            )
            if previous != full_index:
                raise RuntimeError(
                    "split-aware graph merges distinct IceStorm base components"
                )
        self.component_drivers = defaultdict(dict)
        for static, drivers in self.static_drivers.items():
            self.component_drivers[self.base_component[static]].update(drivers)
        self.base_multi_driver_nets = sum(
            len(drivers) > 1 for drivers in self.component_drivers.values()
        )

    def driver_identity(self, segment):
        """Return a physical-source identity, or None for a passive segment."""
        x, y, name = segment
        pll = self.pll_sources.get(segment)
        if pll is not None:
            return pll
        spram = self.spram_sources.get(segment)
        if spram is not None:
            return spram
        oscillator = self.oscillator_sources.get(segment)
        if oscillator is not None:
            return oscillator
        lut = LUT_DRIVER(name)
        if lut and (x, y) in self.ic.logic_tiles:
            index = int(lut.group(1))
            # With no FF, IceStorm models `out` as an alias of combinational
            # `lout`; do not count two names for that one physical source.
            registered = self.icebox.get_lutff_seq_bits(
                self.ic.logic_tiles[(x, y)], index
            )[1] == "1"
            kind = lut.group(2) if registered else "comb"
            return ("lutff", x, y, index, kind)
        io = IO_DRIVER(name)
        if io and (x, y, int(io.group(1))) in self.pll_output_blocks:
            # The PLL owns this IO block.  D_IN_0 was handled above as the PLL
            # core output; no ordinary IO input driver exists alongside it.
            return None
        if io and (x, y) in self.ic.io_tiles:
            return ("io", x, y, name)
        if RAM_DRIVER(name) and (
            (x, y) in self.ic.ramb_tiles or (x, y) in self.ic.ramt_tiles
        ):
            return ("ram", x, y, name)
        if DSP_DRIVER(name) and any((x, y) in tiles for tiles in self.ic.dsp_tiles):
            return ("dsp", x, y, name)
        return None

    def edge_for_segments(self, left, right):
        left = self.segment_to_static[left]
        right = self.segment_to_static[right]
        if left == right:
            return None
        return (left, right) if left < right else (right, left)

    def component_for(self, segment) -> int:
        return self.base_component[self.segment_to_static[segment]]

    def endpoint_drivers(self, x: int, y: int, entry):
        """Return configured drivers on both sides of a proposed route entry."""
        return tuple(
            tuple(
                sorted(
                    self.component_drivers[
                        self.component_for((x, y, endpoint))
                    ].values()
                )
            )
            for endpoint in entry[2:4]
        )

    def addition_creates_multi_driver(self, x: int, y: int, additions) -> bool:
        hit, _drivers = self.mutation_creates_multi_driver(x, y, additions, ())
        return hit

    def mutation_creates_multi_driver(self, x: int, y: int, additions, removals):
        """Return (conflict, driver endpoints) after applying route changes."""
        if removals:
            return self._split_aware_conflict(x, y, additions, removals)

        parents = {}
        drivers = {}

        def root(component: int) -> int:
            parents.setdefault(component, component)
            if parents[component] != component:
                parents[component] = root(parents[component])
            return parents[component]

        def union(left: int, right: int) -> None:
            left = root(left)
            right = root(right)
            if left == right:
                return
            parents[right] = left
            merged = dict(drivers.get(left, self.component_drivers[left]))
            merged.update(drivers.get(right, self.component_drivers[right]))
            drivers[left] = merged

        for entry in additions:
            source = self.component_for((x, y, entry[2]))
            destination = self.component_for((x, y, entry[3]))
            drivers.setdefault(source, self.component_drivers[source])
            drivers.setdefault(destination, self.component_drivers[destination])
            union(source, destination)
        roots = {root(component) for component in parents}
        conflicts = {}
        for component in roots:
            component_drivers = drivers.get(component, self.component_drivers[component])
            if len(component_drivers) > 1:
                conflicts.update(component_drivers)
        return bool(conflicts), tuple(sorted(conflicts.values()))

    def _split_aware_conflict(self, x: int, y: int, additions, removals):
        delta = Counter()
        touched = set()
        changed_adjacency = defaultdict(set)
        for amount, entries in ((1, additions), (-1, removals)):
            for entry in entries:
                edge = self.edge_for_segments(
                    (x, y, entry[2]), (x, y, entry[3])
                )
                if edge is None:
                    continue
                delta[edge] += amount
                touched.update(edge)
                changed_adjacency[edge[0]].add(edge[1])
                changed_adjacency[edge[1]].add(edge[0])
        for edge, amount in delta.items():
            if self.edge_counts[edge] + amount < 0:
                raise RuntimeError(f"route removal underflow for static edge {edge}")

        visited = set()
        conflicts = {}
        for start in touched:
            if start in visited:
                continue
            queue = [start]
            visited.add(start)
            component_drivers = {}
            while queue:
                current = queue.pop()
                component_drivers.update(self.static_drivers[current])
                neighbours = self.adjacency.get(current, set()) | changed_adjacency.get(
                    current, set()
                )
                for neighbour in neighbours:
                    edge = (
                        (current, neighbour)
                        if current < neighbour
                        else (neighbour, current)
                    )
                    if self.edge_counts[edge] + delta[edge] <= 0:
                        continue
                    if neighbour not in visited:
                        visited.add(neighbour)
                        queue.append(neighbour)
            if len(component_drivers) > 1:
                conflicts.update(component_drivers)
        return bool(conflicts), tuple(sorted(conflicts.values()))


def tile_model(ic, x: int, y: int):
    entries = []
    muxes = defaultdict(list)
    bit_to_entries = defaultdict(list)
    for entry in ic.tile_db(x, y):
        if entry[1] not in ("routing", "buffer"):
            continue
        if not ic.tile_has_net(x, y, entry[2]) or not ic.tile_has_net(x, y, entry[3]):
            continue
        index = len(entries)
        entries.append(entry)
        muxes[entry[3]].append(entry)
        for signed_name in entry[0]:
            bit_to_entries[positive_bit_name(signed_name)].append(index)
    return entries, muxes, bit_to_entries


def main() -> int:
    args = arguments()
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(args.asc)
    driver_graph = GlobalDriverGraph(ic, icebox)

    non_zero_tiles = [
        xy for xy, tile in sorted(ic.logic_tiles.items()) if any("1" in row for row in tile)
    ]
    effects = Counter()
    candidate_details = []
    mux_endpoint_count = 0
    jointly_satisfiable_pairs = 0

    for x, y in non_zero_tiles:
        entries, muxes, bit_to_entries = tile_model(ic, x, y)
        tile = ic.logic_tiles[(x, y)]
        bits = signed_tile_bits(tile)
        base = {destination: selected(group, bits) for destination, group in muxes.items()}
        mux_endpoint_count += len(muxes)
        effects["endpoints selected now"] += sum(len(value) == 1 for value in base.values())

        for group in muxes.values():
            for left_index, left in enumerate(group):
                left_polarity = {
                    positive_bit_name(name): name.startswith("!") for name in left[0]
                }
                for right in group[left_index + 1 :]:
                    right_polarity = {
                        positive_bit_name(name): name.startswith("!") for name in right[0]
                    }
                    if all(
                        left_polarity[name] == right_polarity[name]
                        for name in left_polarity.keys() & right_polarity.keys()
                    ):
                        jointly_satisfiable_pairs += 1

        for row in range(ROWS):
            for column in range(COLS):
                name = f"B{row}[{column}]"
                if is_lut_init_position(row, column):
                    effects["LUT-INIT coordinates"] += 1
                touched_indexes = bit_to_entries.get(name)
                if not touched_indexes:
                    effects["non-routing coordinates"] += 1
                    continue
                effects["routing coordinates"] += 1

                was_one = tile[row][column] == "1"
                changed_bits = set(bits)
                changed_bits.discard(("" if was_one else "!") + name)
                changed_bits.add(("!" if was_one else "") + name)
                destinations = {entries[index][3] for index in touched_indexes}
                worst = "no local mux change"
                local_dual_route = False
                for destination in destinations:
                    before = base[destination]
                    after = selected(muxes[destination], changed_bits)
                    if len(after) > 1:
                        worst = "local dual-route candidate"
                        local_dual_route = True
                        break
                    if len(before) == 1 and len(after) == 1 and before != after:
                        worst = "route source changed"
                    elif len(before) == 0 and len(after) == 1 and worst == "no local mux change":
                        worst = "new route entry enabled"
                    elif len(before) == 1 and len(after) == 0 and worst == "no local mux change":
                        worst = "route entry disabled"
                effects[worst] += 1

                # The global check must not be gated on the local dual-route
                # condition.  A clean 0 -> 1 endpoint can still merge two
                # driven components through the full-chip graph.
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

                global_hit = False
                conflict_drivers = ()
                if additions:
                    if removals:
                        effects["split-aware add+remove checks"] += 1
                    global_hit, conflict_drivers = (
                        driver_graph.mutation_creates_multi_driver(
                            x, y, additions, removals
                        )
                    )
                if global_hit:
                    effects["global multi-driver net candidate"] += 1
                    if removals:
                        effects["  of which found after component split"] += 1
                    if not local_dual_route:
                        effects["  of which locally clean (global-only)"] += 1
                        if any(driver[:2] != (x, y) for driver in conflict_drivers):
                            effects["    of which cross-tile"] += 1

                if args.details and (local_dual_route or global_hit):
                    candidate_details.append(
                        (x, y, row, column, additions, removals, conflict_drivers)
                    )

    total_coordinates = len(non_zero_tiles) * ROWS * COLS
    print(f"non-zero logic tiles: {len(non_zero_tiles)} / {len(ic.logic_tiles)}")
    print(f"coordinates checked : {total_coordinates}")
    print(f"local mux endpoints : {mux_endpoint_count}")
    print(f"jointly satisfiable local route pairs: {jointly_satisfiable_pairs}")
    print(f"base global multi-driver nets: {driver_graph.base_multi_driver_nets}")
    print("\n=== exhaustive single-bit flip effects ===")
    order = (
        "endpoints selected now",
        "routing coordinates",
        "non-routing coordinates",
        "LUT-INIT coordinates",
        "new route entry enabled",
        "route source changed",
        "route entry disabled",
        "local dual-route candidate",
        "global multi-driver net candidate",
        "  of which found after component split",
        "  of which locally clean (global-only)",
        "    of which cross-tile",
        "split-aware add+remove checks",
        "no local mux change",
    )
    always_report = {
        "  of which found after component split",
        "split-aware add+remove checks",
    }
    for name in order:
        count = effects[name]
        if count or name in always_report:
            print(f"  {name:<38} {count:8d}")
    if args.details:
        print("\n=== multi-driver candidate details ===")
        for index, (
            x,
            y,
            row,
            column,
            additions,
            removals,
            conflict_drivers,
        ) in enumerate(
            candidate_details, 1
        ):
            print(f"[{index}] tile=({x},{y}) bit=B{row}[{column}]")
            if conflict_drivers:
                print(f"  post-mutation drivers: {conflict_drivers}")
            for action, entries in (("add", additions), ("remove", removals)):
                for entry in entries:
                    source_drivers, destination_drivers = driver_graph.endpoint_drivers(
                        x, y, entry
                    )
                    print(
                        f"  {action}: {entry[2]} -> {entry[3]} "
                        f"source_drivers={source_drivers or '-'} "
                        f"destination_drivers={destination_drivers or '-'}"
                    )
    print(
        "\nDriver boundary: LUT/IO-input/RAM-read/UP5K-DSP/PLL/SPRAM/oscillator "
        "outputs; "
        "oscillator and other hard-IP coverage is not complete."
    )
    print(
        "Model boundary: database structure + IceStorm global net graph; "
        "no silicon measurement."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

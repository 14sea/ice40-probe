#!/usr/bin/env python3
"""Independent conflict oracle for single-bit routing mutations.

This tool exists to cross-check `exhaustive.py`, so it deliberately shares no
conflict logic with it:

  * flip enumeration is re-implemented here from `ic.tile_db()` directly;
  * the verdict is obtained by mutating the configuration in place and asking
    IceStorm to rebuild its ENTIRE segment graph (`ic.group_segments()`), then
    counting distinct driver identities per component -- no incremental graph,
    no union-find, no static/programmable decomposition;
  * `exhaustive.GlobalDriverGraph` is imported for COMPARISON ONLY, so that a
    disagreement between model and oracle is reported rather than hidden.

Shared assumption worth stating: both sides treat `lutff_N/out` and
`lutff_N/lout` as one physical source when the LC's DffEnable bit is clear.
That is a claim about the silicon, not about either implementation, so it is
not independently tested here.

`glb_netwk_*` is deliberately NOT treated as a driver: it is a distribution
network, not a source.  When configuration connects a PLL output to one, the
PLL identity is annotated on that passive endpoint.  Oscillators and other
hard-IP sources are not modelled yet -- see the coverage note printed at the
end of a run.

The full adds-only sweep over `leds` is ~49k rebuilds, so runs are resumable:
every checked flip is appended to a JSONL result file that also records the ASC
hash and IceStorm version it belongs to.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from multiprocessing import Pool
from pathlib import Path
import random
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from iceutil import COLS, ROWS, load_icebox, signed_tile_bits  # noqa: E402

# Driver identities.  A distribution network (glb_netwk_*) is not a source.
LUT_DRIVER = re.compile(r"lutff_([0-7])/(out|lout)").fullmatch
IO_DRIVER = re.compile(r"io_([01])/D_IN_([01])").fullmatch
RAM_DRIVER = re.compile(r"ram/RDATA_\d+").fullmatch
DSP_DRIVER = re.compile(r"mult/O_\d+").fullmatch
PLL_CONFIG_BIT = re.compile(r"B(\d+)\[(\d+)\]").fullmatch

STATE: dict = {}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("asc", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="JSONL result file")
    parser.add_argument(
        "--flip-class",
        choices=("adds", "addrem"),
        default="adds",
        help="adds: flips that only enable routes; addrem: flips that do both",
    )
    parser.add_argument("--sample", type=int, default=0, help="0 = sweep the whole class")
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=7)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--progress-every", type=int, default=200)
    parser.add_argument(
        "--expect-positives",
        type=int,
        default=None,
        help="fail the report unless exactly this many oracle positives are found",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="re-read an existing result file and print the acceptance summary",
    )
    return parser.parse_args()


def toolchain_identity(icebox) -> dict:
    """Identify everything whose change invalidates a previous run's records."""
    module = Path(icebox.__file__)
    try:
        version = subprocess.run(
            ["dpkg-query", "-W", "-f=${Version}", "fpga-icestorm"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        version = "unknown"
    return {
        "icebox_module": str(module),
        "icebox_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "icestorm_package": version,
        # The verdict depends on the model code as much as on the database, so
        # a resume must not reuse records produced by a different model.
        "oracle_sha256": hashlib.sha256((HERE / "oracle.py").read_bytes()).hexdigest(),
        "exhaustive_sha256": hashlib.sha256(
            (HERE / "exhaustive.py").read_bytes()
        ).hexdigest(),
    }


def read_records(path: Path):
    """Read a result file, tolerating a half-line left by an interrupted run.

    A killed writer can leave a partial final line.  Malformed lines are
    dropped and the file is rewritten from the surviving records so that the
    next append starts on a clean boundary.
    """
    header = None
    records = {}
    malformed = 0
    duplicates = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        kind = record.get("record")
        if kind == "header":
            header = record
            continue
        if kind == "summary":
            continue
        key = (record["x"], record["y"], record["row"], record["column"])
        if key in records:
            duplicates += 1
        records[key] = record
    if malformed:
        rewritten = [json.dumps(header)] if header else []
        rewritten += [json.dumps(record) for record in records.values()]
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
        temporary.replace(path)
    return header, records, malformed, duplicates


def acceptance_report(
    path: Path, expected_targets: int | None, expected_positives: int | None = None
) -> int:
    header, records, malformed, duplicates = read_records(path)
    summary = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith('{"record": "summary"'):
            summary = json.loads(line)
    positives = [record for record in records.values() if record["oracle"]]
    disagreements = [record for record in records.values() if not record["agree"]]
    wrong_delta = [
        record for record in positives if record["oracle_conflict_nets"] != 1
    ]
    print("=== acceptance report ===")
    if header:
        print(f"asc                : {header['asc']}")
        print(f"asc sha256         : {header['asc_sha256']}")
        print(f"icebox sha256      : {header['icebox_sha256']}")
        print(f"oracle sha256      : {header.get('oracle_sha256', '(not recorded)')}")
        print(f"exhaustive sha256  : {header.get('exhaustive_sha256', '(not recorded)')}")
        print(f"icestorm package   : {header['icestorm_package']}")
        print(f"flip class         : {header['flip_class']}")
        print(f"targets in header  : {header.get('targets', '?')}")
    if summary:
        print(f"workers            : {summary['workers']}")
        print(f"elapsed            : {summary['elapsed_seconds'] / 60:.1f} min")
    print(f"unique coordinates : {len(records)}")
    print(f"duplicate lines    : {duplicates}")
    print(f"malformed lines    : {malformed} (dropped, file rewritten)" if malformed
          else "malformed lines    : 0")
    print(f"oracle positives   : {len(positives)}")
    print(f"positives with net delta != 1 : {len(wrong_delta)}")
    print(f"model/oracle disagreements    : {len(disagreements)}")
    failures = []
    expected = expected_targets or (header or {}).get("targets")
    if expected is not None and len(records) != expected:
        failures.append(f"coordinate count {len(records)} != expected {expected}")
    if duplicates:
        failures.append(f"{duplicates} duplicate coordinates")
    if wrong_delta:
        failures.append(f"{len(wrong_delta)} positives whose conflict delta is not 1")
    if disagreements:
        failures.append(f"{len(disagreements)} model/oracle disagreements")
    if expected_positives is not None and len(positives) != expected_positives:
        failures.append(
            f"oracle positives {len(positives)} != expected {expected_positives}"
        )
    for record in sorted(
        positives, key=lambda item: (item["x"], item["y"], item["row"], item["column"])
    ):
        print(
            f"  positive tile=({record['x']},{record['y']}) "
            f"bit=B{record['row']}[{record['column']}] "
            f"delta={record['oracle_conflict_nets']}"
        )
    if failures:
        print("\nFAIL: " + "; ".join(failures))
        return 1
    print("\nPASS: coordinates complete and unique, deltas are +1, model agrees")
    return 0


def pll_driver_state(ic, icebox):
    """Independently decode active PLL core/global source annotations."""
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


def driver_identity(ic, icebox, segment, pll_sources=None, pll_blocks=None,
                    spram_sources=None, oscillator_sources=None):
    x, y, name = segment
    if pll_sources is None or pll_blocks is None:
        pll_sources, pll_blocks = pll_driver_state(ic, icebox)
    if spram_sources is None:
        spram_sources = spram_driver_state(ic)
    if oscillator_sources is None:
        oscillator_sources = oscillator_driver_state(ic, pll_sources)
    pll = pll_sources.get(segment)
    if pll is not None:
        return pll
    spram = spram_sources.get(segment)
    if spram is not None:
        return spram
    oscillator = oscillator_sources.get(segment)
    if oscillator is not None:
        return oscillator
    lut = LUT_DRIVER(name)
    if lut and (x, y) in ic.logic_tiles:
        index = int(lut.group(1))
        registered = icebox.get_lutff_seq_bits(ic.logic_tiles[(x, y)], index)[1] == "1"
        return ("lutff", x, y, index, lut.group(2) if registered else "comb")
    io = IO_DRIVER(name)
    if io and (x, y, int(io.group(1))) in pll_blocks:
        return None
    if io and (x, y) in ic.io_tiles:
        return ("io", x, y, name)
    if RAM_DRIVER(name) and ((x, y) in ic.ramb_tiles or (x, y) in ic.ramt_tiles):
        return ("ram", x, y, name)
    if DSP_DRIVER(name) and any((x, y) in tiles for tiles in ic.dsp_tiles):
        return ("dsp", x, y, name)
    return None


def conflicting_nets(ic, icebox) -> int:
    """Rebuild the whole graph and count nets carrying more than one source."""
    total = 0
    pll_sources, pll_blocks = pll_driver_state(ic, icebox)
    for segments in ic.group_segments():
        identities = {
            driver_identity(ic, icebox, segment, pll_sources, pll_blocks)
            for segment in segments
        }
        identities.discard(None)
        if len(identities) > 1:
            total += 1
    return total


def tile_routing_entries(ic, x: int, y: int):
    entries = []
    bit_to_entries = defaultdict(list)
    for entry in ic.tile_db(x, y):
        if entry[1] not in ("routing", "buffer"):
            continue
        if not ic.tile_has_net(x, y, entry[2]) or not ic.tile_has_net(x, y, entry[3]):
            continue
        index = len(entries)
        entries.append(entry)
        for signed in entry[0]:
            bit_to_entries[signed[1:] if signed.startswith("!") else signed].append(index)
    return entries, bit_to_entries


def enumerate_flips(ic, flip_class: str):
    """Yield (x, y, row, column) for every flip of the requested class."""
    for (x, y), tile in sorted(ic.logic_tiles.items()):
        if not any("1" in row for row in tile):
            continue
        entries, bit_to_entries = tile_routing_entries(ic, x, y)
        bits = signed_tile_bits(tile)
        for row in range(ROWS):
            for column in range(COLS):
                name = f"B{row}[{column}]"
                indexes = bit_to_entries.get(name)
                if not indexes:
                    continue
                was_one = tile[row][column] == "1"
                changed = set(bits)
                changed.discard(("" if was_one else "!") + name)
                changed.add(("!" if was_one else "") + name)
                additions = removals = 0
                for index in indexes:
                    entry = entries[index]
                    before = all(bit in bits for bit in entry[0])
                    after = all(bit in changed for bit in entry[0])
                    additions += after and not before
                    removals += before and not after
                if not additions:
                    continue
                if flip_class == "adds" and removals:
                    continue
                if flip_class == "addrem" and not removals:
                    continue
                yield (x, y, row, column)


def initialise(asc: str) -> None:
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(asc)
    from exhaustive import GlobalDriverGraph  # comparison only

    STATE.update(
        icebox=icebox,
        ic=ic,
        graph=GlobalDriverGraph(ic, icebox),
        base=conflicting_nets(ic, icebox),
        models={},
    )


def check(target):
    x, y, row, column = target
    ic = STATE["ic"]
    icebox = STATE["icebox"]
    if (x, y) not in STATE["models"]:
        STATE["models"][(x, y)] = tile_routing_entries(ic, x, y)
    entries, bit_to_entries = STATE["models"][(x, y)]
    tile = ic.logic_tiles[(x, y)]
    bits = signed_tile_bits(tile)
    name = f"B{row}[{column}]"
    was_one = tile[row][column] == "1"
    changed = set(bits)
    changed.discard(("" if was_one else "!") + name)
    changed.add(("!" if was_one else "") + name)

    additions, removals = [], []
    for index in bit_to_entries[name]:
        entry = entries[index]
        before = all(bit in bits for bit in entry[0])
        after = all(bit in changed for bit in entry[0])
        if after and not before:
            additions.append(entry)
        elif before and not after:
            removals.append(entry)

    model_hit, _drivers = STATE["graph"].mutation_creates_multi_driver(
        x, y, additions, removals
    )

    original = tile[row]
    tile[row] = original[:column] + ("0" if was_one else "1") + original[column + 1 :]
    try:
        oracle_nets = conflicting_nets(ic, icebox)
    finally:
        tile[row] = original
    oracle_hit = oracle_nets > STATE["base"]
    return {
        "x": x,
        "y": y,
        "row": row,
        "column": column,
        "oracle_conflict_nets": oracle_nets - STATE["base"],
        "oracle": bool(oracle_hit),
        "model": bool(model_hit),
        "agree": bool(oracle_hit) == bool(model_hit),
    }


def main() -> int:
    args = arguments()
    if args.report:
        return acceptance_report(args.out, None, args.expect_positives)
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(args.asc))

    header = {
        "record": "header",
        "asc": str(args.asc),
        "asc_sha256": hashlib.sha256(args.asc.read_bytes()).hexdigest(),
        "flip_class": args.flip_class,
        "sample": args.sample,
        "seed": args.seed,
        **toolchain_identity(icebox),
    }

    targets = list(enumerate_flips(ic, args.flip_class))
    if args.sample:
        random.seed(args.seed)
        targets = sorted(random.sample(targets, min(args.sample, len(targets))))
    header["targets"] = len(targets)

    done = {}
    if args.out.exists():
        previous_header, done, malformed, duplicates = read_records(args.out)
        if malformed:
            print(f"dropped {malformed} malformed line(s) from an interrupted run")
        if duplicates:
            print(f"warning: {duplicates} duplicate coordinate line(s) collapsed")
        if previous_header is not None:
            mismatched = [
                key
                for key in (
                    "asc_sha256",
                    "flip_class",
                    "icebox_sha256",
                    "oracle_sha256",
                    "exhaustive_sha256",
                    "sample",
                    "seed",
                )
                if previous_header.get(key) != header.get(key)
            ]
            if mismatched:
                print(
                    f"refusing to resume {args.out}: differs in {', '.join(mismatched)}",
                    file=sys.stderr,
                )
                return 2
        print(f"resuming: {len(done)} of {len(targets)} already recorded")

    remaining = [target for target in targets if target not in done]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if not args.out.exists():
        with args.out.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(header) + "\n")

    print(
        f"asc={args.asc} sha256={header['asc_sha256'][:16]}… "
        f"icestorm={header['icestorm_package']}"
    )
    print(
        f"class={args.flip_class} targets={len(targets)} remaining={len(remaining)} "
        f"workers={args.workers}"
    )

    disagreements = [record for record in done.values() if not record["agree"]]
    positives = [record for record in done.values() if record["oracle"]]
    started = time.time()
    completed = 0
    with args.out.open("a", encoding="utf-8") as handle:
        with Pool(args.workers, initializer=initialise, initargs=(str(args.asc),)) as pool:
            for record in pool.imap_unordered(check, remaining, chunksize=16):
                handle.write(json.dumps(record) + "\n")
                handle.flush()
                completed += 1
                if record["oracle"]:
                    positives.append(record)
                if not record["agree"]:
                    disagreements.append(record)
                    print(
                        f"  DISAGREE tile=({record['x']},{record['y']}) "
                        f"bit=B{record['row']}[{record['column']}] "
                        f"oracle={record['oracle']} model={record['model']}"
                    )
                if completed % args.progress_every == 0:
                    elapsed = time.time() - started
                    rate = completed / elapsed
                    left = (len(remaining) - completed) / rate if rate else 0
                    print(
                        f"  {completed}/{len(remaining)}  {elapsed / 60:.1f} min  "
                        f"eta {left / 60:.1f} min  positives={len(positives)}",
                        flush=True,
                    )

    summary = {
        "record": "summary",
        "asc": header["asc"],
        "asc_sha256": header["asc_sha256"],
        "icebox_sha256": header["icebox_sha256"],
        "icestorm_package": header["icestorm_package"],
        "flip_class": header["flip_class"],
        "workers": args.workers,
        "elapsed_seconds": round(time.time() - started, 1),
        "checked_this_run": completed,
        "coordinates": len(done) + completed,
        "targets": len(targets),
        "positives": len(positives),
        "disagreements": len(disagreements),
    }
    with args.out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary) + "\n")

    print(f"\nchecked {len(done) + completed} / {len(targets)} flips in this class")
    print(
        f"workers={args.workers} elapsed={summary['elapsed_seconds'] / 60:.1f} min "
        f"asc_sha256={header['asc_sha256'][:16]}… icestorm={header['icestorm_package']}"
    )
    print(f"oracle positives : {len(positives)}")
    print(f"model/oracle disagreements: {len(disagreements)}")
    for record in sorted(
        disagreements, key=lambda item: (item["x"], item["y"], item["row"], item["column"])
    ):
        print(
            f"  tile=({record['x']},{record['y']}) bit=B{record['row']}[{record['column']}] "
            f"oracle={record['oracle']} model={record['model']}"
        )
    print("\nPositive coordinates:")
    for record in sorted(
        positives, key=lambda item: (item["x"], item["y"], item["row"], item["column"])
    ):
        print(f"  tile=({record['x']},{record['y']}) bit=B{record['row']}[{record['column']}]")
    print(
        "\nDriver identities: LUT/IO-input/RAM-read/UP5K-DSP/PLL/SPRAM outputs. "
        "glb_netwk_* is a distribution network and is not counted as a source; "
        "other hard-IP outputs remain outside this oracle's coverage."
    )
    return 1 if disagreements else 0


if __name__ == "__main__":
    raise SystemExit(main())

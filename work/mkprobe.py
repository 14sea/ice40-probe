#!/usr/bin/env python3
"""Create a LUT-inversion probe and reject observationally ambiguous results."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

from iceutil import LUT_BITNUMS, SEQ_BITNUMS


HERE = Path(__file__).resolve().parent
PINS = {"io_4_31_0": "B", "io_5_31_0": "R", "io_6_31_0": "G"}
COLOURS = {
    (0, 0, 0): "黑",
    (0, 0, 1): "紅",
    (0, 1, 0): "綠",
    (0, 1, 1): "黃",
    (1, 0, 0): "藍",
    (1, 0, 1): "洋紅",
    (1, 1, 0): "青",
    (1, 1, 1): "白",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("tile_x", type=int)
    parser.add_argument("tile_y", type=int)
    parser.add_argument("lc", type=int, choices=range(8))
    parser.add_argument("output_prefix", type=Path)
    parser.add_argument("--source-asc", type=Path, default=HERE / "leds.asc")
    parser.add_argument("--baseline-vlog", type=Path, default=HERE / "leds_rt.v")
    parser.add_argument(
        "--allow-indistinguishable",
        action="store_true",
        help="return success after creating an ambiguous negative-test artifact",
    )
    return parser.parse_args()


def location(bitnum: int, lc: int) -> tuple[int, int]:
    return 2 * lc + (0 if bitnum < 10 else 1), 36 + (bitnum if bitnum < 10 else bitnum - 10)


def invert_lut(source: Path, destination: Path, tile_x: int, tile_y: int, lc: int) -> None:
    lines = source.read_text(encoding="utf-8").splitlines()
    marker = f".logic_tile {tile_x} {tile_y}"
    try:
        start = lines.index(marker)
    except ValueError as error:
        raise ValueError(f"logic tile not found: ({tile_x}, {tile_y})") from error
    rows = lines[start + 1 : start + 17]
    if len(rows) != 16 or any(len(row) != 54 for row in rows):
        raise ValueError(f"malformed logic tile at ({tile_x}, {tile_y})")

    sequence_before = [rows[location(bit, lc)[0]][location(bit, lc)[1]] for bit in SEQ_BITNUMS]
    for bitnum in LUT_BITNUMS:
        row, column = location(bitnum, lc)
        values = list(rows[row])
        values[column] = "1" if values[column] == "0" else "0"
        rows[row] = "".join(values)
    sequence_after = [rows[location(bit, lc)[0]][location(bit, lc)[1]] for bit in SEQ_BITNUMS]
    if sequence_before != sequence_after:
        raise AssertionError("LC sequential-control bits changed")
    lines[start + 1 : start + 17] = rows
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")


def decode_asc(source: Path, destination: Path) -> None:
    with destination.open("w", encoding="utf-8") as output:
        subprocess.run(
            ["icebox_vlog", str(source)],
            check=True,
            stdout=output,
            stderr=subprocess.DEVNULL,
            text=True,
        )


def pin_luts(vlog_path: Path):
    source = vlog_path.read_text(encoding="utf-8")
    result = {}
    for pin, colour in PINS.items():
        output = re.search(rf"assign {re.escape(pin)} = (\w+);", source)
        if not output:
            raise ValueError(f"{pin} is not a direct combinational assignment in {vlog_path}")
        lut = re.search(
            rf"assign {re.escape(output.group(1))} = /\* LUT +(\d+) +(\d+) +(\d+) \*/ ([^;]+);",
            source,
        )
        if not lut:
            raise ValueError(f"cannot find the LUT driving {pin} in {vlog_path}")
        result[colour] = (
            lut.group(4).strip(),
            (int(lut.group(1)), int(lut.group(2)), int(lut.group(3))),
        )
    return result


def simple_boolean(expression: str, values: dict[str, int]) -> int:
    """Evaluate only the one-net expressions expected from this LED probe."""
    match = re.fullmatch(r"(!?)(n\d+|1'b[01])", expression.strip())
    if not match:
        raise ValueError(f"unsupported LUT expression: {expression!r}")
    token = match.group(2)
    if token.startswith("1'b"):
        value = int(token[-1])
    elif token in values:
        value = values[token]
    else:
        raise ValueError(f"unsupported probe input net: {token}")
    return 1 - value if match.group(1) else value


def sequence(vlog_path: Path):
    luts = pin_luts(vlog_path)
    output = []
    for counter_25 in (0, 1):
        for counter_24 in (0, 1):
            for counter_23 in (0, 1):
                values = {"n24": counter_23, "n25": counter_24, "n26": counter_25}
                led_on = tuple(
                    0 if simple_boolean(luts[colour][0], values) else 1
                    for colour in ("B", "G", "R")
                )
                output.append(COLOURS[led_on])
    return luts, output


def rotations(values: list[str]):
    return {tuple(values[index:] + values[:index]) for index in range(len(values))}


def main() -> int:
    args = arguments()
    prefix = args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    asc_path = prefix.with_suffix(".asc")
    bin_path = prefix.with_suffix(".bin")
    vlog_path = prefix.with_suffix(".v")
    if asc_path.resolve() == args.source_asc.resolve():
        raise ValueError("output ASC must not overwrite the source ASC")

    invert_lut(args.source_asc, asc_path, args.tile_x, args.tile_y, args.lc)
    subprocess.run(["icepack", str(asc_path), str(bin_path)], check=True)
    decode_asc(asc_path, vlog_path)
    baseline_luts, baseline = sequence(args.baseline_vlog)
    mutant_luts, mutant = sequence(vlog_path)

    print("baseline 循環: " + " → ".join(baseline))
    print("mutant   循環: " + " → ".join(mutant))
    print(
        "LUT 變更:",
        {
            colour: (baseline_luts[colour][0], mutant_luts[colour][0])
            for colour in "RGB"
            if baseline_luts[colour][0] != mutant_luts[colour][0]
        },
    )
    distinguishable = tuple(mutant) not in rotations(baseline)
    if distinguishable:
        print("鑑別力檢查: PASS -- 不是 baseline 的任何一個旋轉")
        return 0
    print("鑑別力檢查: FAIL -- 只是相位平移，不應燒錄")
    return 0 if args.allow_indistinguishable else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error

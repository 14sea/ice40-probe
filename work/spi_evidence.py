#!/usr/bin/env python3
"""Rebuild the measurements the SB_SPI driver identity rests on.

Two facts underneath `spi_check.py` would otherwise be quotations from a
build log, which cannot be re-checked when the toolchain changes:

  1. **Which BUS_ADDR74 values exist, and which instance each selects.**  An
     SB_SPI is not placed by a constraint; nextpnr reads this parameter and
     rejects anything it does not recognise.  All sixteen four-bit values are
     built here and the outcome is parsed from the placer's own report, so the
     mapping is enumerated rather than copied: "0b0000" -> X0/Y0/spi_0,
     "0b0010" -> X25/Y0/spi_1, and the remaining fourteen are refused.

  2. **The enable vector that means "enabled".**  The model treats an instance
     as driving the fabric only when the whole set of `SPI_ENABLE` bits named
     by the cell database is set, so that pattern has to be observed, not
     assumed.  Each instance is built alone: its own four bits read 1, the
     other instance's four read 0, and a design with no SPI at all reads 0 for
     all eight.  Without the last two checks, "the bits are set" could just
     mean the bits are always set.

Host-only: sixteen designs are synthesised and placed, none is programmed.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = ROOT / "build" / "spi_evidence"
sys.path.insert(0, str(HERE))

from exhaustive import (  # noqa: E402
    enable_gated_cells,
    enable_gated_enable_bits,
    enable_gated_fabric_endpoints,
    ipconfig_bit,
)
from iceutil import load_icebox  # noqa: E402

failures: list[str] = []

PCF = """set_io clk 35
set_io LED_R 40
set_io LED_G 41
set_io LED_B 39
"""

# One instance, every output consumed.  A design that leaves outputs open
# routes fewer endpoints and would understate the block, which is exactly how
# the inventory first reported nineteen instead of twenty-five.
ONE_SPI = """module top(input clk, output LED_R, output LED_G, output LED_B);
    reg [7:0] address = 0;
    reg strobe = 0, serial_in = 0, serial_clock = 0, chip_select = 0, master_in = 0;
    always @(posedge clk) begin
        address <= address + 1'b1; strobe <= ~strobe;
        serial_in <= ~serial_in; serial_clock <= serial_in;
        chip_select <= serial_clock; master_in <= chip_select;
    end
    wire [7:0] data; wire [3:0] csn, csn_oe;
    wire ack, irq, wakeup, so, so_oe, mo, mo_oe, sck, sck_oe;
    SB_SPI #(.BUS_ADDR74("%(bus_address)s")) spi (
        .SBCLKI(clk), .SBRWI(1'b1), .SBSTBI(strobe),
        .SBADRI7(address[7]), .SBADRI6(address[6]), .SBADRI5(address[5]),
        .SBADRI4(address[4]), .SBADRI3(address[3]), .SBADRI2(address[2]),
        .SBADRI1(address[1]), .SBADRI0(address[0]),
        .SBDATI7(1'b0), .SBDATI6(1'b0), .SBDATI5(1'b0), .SBDATI4(1'b0),
        .SBDATI3(1'b0), .SBDATI2(1'b0), .SBDATI1(1'b0), .SBDATI0(1'b0),
        .MI(master_in), .SI(serial_in), .SCKI(serial_clock), .SCSNI(chip_select),
        .SBDATO7(data[7]), .SBDATO6(data[6]), .SBDATO5(data[5]), .SBDATO4(data[4]),
        .SBDATO3(data[3]), .SBDATO2(data[2]), .SBDATO1(data[1]), .SBDATO0(data[0]),
        .SBACKO(ack), .SPIIRQ(irq), .SPIWKUP(wakeup),
        .SO(so), .SOE(so_oe), .MO(mo), .MOE(mo_oe), .SCKO(sck), .SCKOE(sck_oe),
        .MCSNO0(csn[0]), .MCSNO1(csn[1]), .MCSNO2(csn[2]), .MCSNO3(csn[3]),
        .MCSNOE0(csn_oe[0]), .MCSNOE1(csn_oe[1]),
        .MCSNOE2(csn_oe[2]), .MCSNOE3(csn_oe[3]));
    assign LED_R = ~(^data ^ so ^ so_oe ^ mo ^ mo_oe);
    assign LED_G = ~(ack ^ irq ^ wakeup ^ sck ^ sck_oe);
    assign LED_B = ~(^csn ^ ^csn_oe);
endmodule
"""

EXPECTED_PLACEMENTS = {"0b0000": "X0/Y0/spi_0", "0b0010": "X25/Y0/spi_1"}


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def build(name: str, verilog: str) -> dict:
    """Synthesise and place one design, recording where it stopped.

    Which stage rejects a design is part of the claim: "the placer refuses the
    other fourteen values" is a different statement from "they do not build",
    and a check that only counts the survivors cannot tell the two apart.  So
    the synthesis result, the placer's exit status and its error line are all
    returned, and asserted separately below.
    """
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / f"{name}.v").write_text(verilog, encoding="utf-8")
    (BUILD / f"{name}.pcf").write_text(PCF, encoding="utf-8")
    synthesis = subprocess.run(
        ["yosys", "-q", "-l", str(BUILD / f"{name}_yosys.log"), "-p",
         f"synth_ice40 -json {BUILD / f'{name}.json'}", str(BUILD / f"{name}.v")],
        capture_output=True, text=True,
    )
    result = {
        "synthesised": synthesis.returncode == 0,
        "placer_status": None,
        "error": "",
        "asc": None,
        "placement": "",
    }
    if synthesis.returncode:
        result["error"] = "yosys rejected the design"
        return result
    placement = subprocess.run(
        ["nextpnr-ice40", "--up5k", "--package", "sg48",
         "--json", str(BUILD / f"{name}.json"), "--pcf", str(BUILD / f"{name}.pcf"),
         "--asc", str(BUILD / f"{name}.asc"), "--freq", "12",
         "--log", str(BUILD / f"{name}_pnr.log")],
        capture_output=True, text=True,
    )
    log = (BUILD / f"{name}_pnr.log").read_text(encoding="utf-8")
    result["placer_status"] = placement.returncode
    if placement.returncode:
        error = re.search(r"ERROR: (.+)", log)
        result["error"] = error.group(1).strip() if error else "nextpnr failed"
        return result
    located = re.search(r"constrained SB_SPI '\w+' to (\S+)", log)
    result["asc"] = BUILD / f"{name}.asc"
    result["placement"] = located.group(1) if located else "?"
    return result


def main() -> int:
    icebox = load_icebox()
    cells = dict(enable_gated_cells(icebox, "SPI"))

    print("=== BUS_ADDR74: every four-bit value, built ===")
    results = {}
    for value in range(16):
        parameter = f"0b{value:04b}"
        results[parameter] = build(
            f"bus_{value:04b}", ONE_SPI % {"bus_address": parameter}
        )
        outcome = results[parameter]
        print(
            f"  {parameter}: "
            + (
                f"placed at {outcome['placement']}"
                if outcome["asc"]
                else f"rejected at "
                f"{'synthesis' if not outcome['synthesised'] else 'placement'}"
                f" -- {outcome['error']}"
            )
        )
    accepted = {
        parameter: outcome
        for parameter, outcome in results.items()
        if outcome["asc"] is not None
    }
    rejected = {
        parameter: outcome
        for parameter, outcome in results.items()
        if outcome["asc"] is None
    }
    check(
        "exactly two values are accepted",
        sorted(accepted) == sorted(EXPECTED_PLACEMENTS),
        f"{sorted(accepted)}",
    )
    check(
        "and each selects the instance the database describes",
        {name: outcome["placement"] for name, outcome in accepted.items()}
        == EXPECTED_PLACEMENTS,
        f"{ {name: outcome['placement'] for name, outcome in accepted.items()} }",
    )
    # The fourteen refusals matter -- they are why a fixture cannot pick an
    # instance by placement constraint -- and *where* they are refused matters
    # too.  Counting survivors alone would report "the placer refuses them"
    # even if they had failed one stage earlier, in synthesis.
    check(
        "the other fourteen all synthesise",
        all(outcome["synthesised"] for outcome in rejected.values()),
        f"{sorted(name for name, o in rejected.items() if not o['synthesised'])}",
    )
    check(
        "and are then refused by the placer, with a non-zero exit",
        len(rejected) == 14
        and all(outcome["placer_status"] for outcome in rejected.values()),
        f"{len(rejected)} rejected, statuses "
        f"{sorted({outcome['placer_status'] for outcome in rejected.values()})}",
    )
    check(
        "each for this parameter, not for some unrelated reason",
        all(
            "Invalid value for BUS_ADDR74" in outcome["error"]
            for outcome in rejected.values()
        ),
        f"{sorted({outcome['error'][:48] for outcome in rejected.values()})}",
    )

    print("\n=== the enable vector, read back from each instance alone ===")
    placement_for_parameter = {
        "0b0000": (0, 0, 0),
        "0b0010": (25, 0, 1),
    }
    for parameter, outcome in sorted(accepted.items()):
        active = icebox.iceconfig()
        active.read_file(str(outcome["asc"]))
        placed = placement_for_parameter[parameter]
        for placement, cell in sorted(cells.items()):
            bits = enable_gated_enable_bits(cell, "SPI")
            values = [ipconfig_bit(active, x, y, name) for x, y, name in bits]
            expected = ["1"] * len(bits) if placement == placed else ["0"] * len(bits)
            check(
                f"{parameter}: instance {placement} reads {''.join(expected)}",
                values == expected,
                f"read {''.join(str(value) for value in values)} "
                f"at {[(x, y) for x, y, _n in bits]}",
            )
        endpoints = set(enable_gated_fabric_endpoints(cells[placed]))
        present = {
            segment
            for group in active.group_segments()
            for segment in group
            if "slf_op" in segment[2]
        }
        check(
            f"{parameter}: its twenty-five endpoints are all routed",
            len(endpoints) == 25 and not (endpoints - present),
            f"{len(endpoints)} stated, {len(endpoints - present)} unrouted",
        )
        check(
            f"{parameter}: and no other block's endpoint appears",
            not (present - endpoints),
            f"{sorted(present - endpoints)[:3]}",
        )

    leds = icebox.iceconfig()
    leds.read_file(str(ROOT / "build" / "leds.asc"))
    for placement, cell in sorted(cells.items()):
        bits = enable_gated_enable_bits(cell, "SPI")
        values = [ipconfig_bit(leds, x, y, name) for x, y, name in bits]
        check(
            f"a design with no SPI reads all-clear for {placement}",
            values == ["0"] * len(bits),
            f"read {''.join(str(value) for value in values)}",
        )

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: BUS_ADDR74 mapping and the SPI enable vector, both rebuilt")
    print(
        "Boundary: this establishes which parameter values nextpnr accepts and "
        "what a placed instance writes.  What an individual SPI_ENABLE bit "
        "means is not established here, and no bit pattern in these designs "
        "separates them."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Inventory: which UP5K hard IP actually drives the programmable fabric.

This is the survey step that decides whether a fixture is warranted, run before
any identity is written.  The protocol it follows:

  1. establish whether the IP has an output that enters the fabric at all;
  2. for those that do, record the endpoints and the enabling configuration;
  3. for those that only reach package pins, mark them as not applicable to the
     driver graph rather than forcing them into it;
  4. where the evidence is insufficient, say undetermined -- never report
     "no path" as a conclusion from an enumeration that was not shown complete;
  5. only build a fixture once a fabric path is confirmed.

Point 4 is not boilerplate.  This project has twice produced a clean-looking
negative from an incomplete enumeration, so a negative here is only recorded
when it rests on more than one independent observation.

Host-only: every design is synthesised and placed, never programmed.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = ROOT / "build" / "inventory"
sys.path.insert(0, str(HERE))

from exhaustive import GlobalDriverGraph, ipconfig_bit  # noqa: E402
from iceutil import load_icebox  # noqa: E402

# icebox's own cell database, which states every hard-IP port as a segment and
# every enabling bit as a coordinate.  It is the authority here; the synthesised
# designs below are the check on it, not the other way round.  Reading a count
# off a design instead would measure the testbench: the SPI figure this file
# first reported was 19 because the fixture drove one chip select out of four.
PLACEMENTS = {
    "i2c": ("I2C", (0, 31, 0)),
    "spi": ("SPI", (0, 0, 0)),
    "ledda": ("LEDDA_IP", (0, 31, 2)),
    "rgba": ("RGBA_DRV", (0, 30, 0)),
}


def cell_ports(icebox, name: str) -> dict:
    kind, placement = PLACEMENTS[name]
    for key, cell in icebox.extra_cells_db["5k"].items():
        if key[0] == kind and key[1] == placement:
            return cell
    raise KeyError(f"{kind} at {placement} is not in extra_cells_db['5k']")


def db_endpoints(cell: dict) -> set:
    return {
        (value[0], value[1], value[2])
        for value in cell.values()
        if isinstance(value, tuple) and len(value) == 3
        and str(value[2]).startswith("slf_op")
    }


def db_enable_bits(cell: dict) -> dict:
    return {
        port: value for port, value in cell.items()
        if "ENABLE" in port or port.endswith("_EN")
    }

failures: list[str] = []

LEDS = "set_io LED_R 40\nset_io LED_G 41\nset_io LED_B 39\n"

I2C = """module top(input clk, inout SCL, inout SDA, output LED_R, output LED_G, output LED_B);
   reg [7:0] addr = 0; reg stb = 0;
   always @(posedge clk) begin addr <= addr + 1'b1; stb <= ~stb; end
   wire [7:0] dato; wire ack, irq, wkup, sclo, scloe, sdao, sdaoe;
   SB_I2C #(.I2C_SLAVE_INIT_ADDR("0b1111100001"), .BUS_ADDR74("0b0001")) i2c (
      .SBCLKI(clk), .SBRWI(1'b1), .SBSTBI(stb),
      .SBADRI7(addr[7]), .SBADRI6(addr[6]), .SBADRI5(addr[5]), .SBADRI4(addr[4]),
      .SBADRI3(addr[3]), .SBADRI2(addr[2]), .SBADRI1(addr[1]), .SBADRI0(addr[0]),
      .SBDATI7(1'b0), .SBDATI6(1'b0), .SBDATI5(1'b0), .SBDATI4(1'b0),
      .SBDATI3(1'b0), .SBDATI2(1'b0), .SBDATI1(1'b0), .SBDATI0(1'b0),
      .SCLI(SCL), .SDAI(SDA),
      .SBDATO7(dato[7]), .SBDATO6(dato[6]), .SBDATO5(dato[5]), .SBDATO4(dato[4]),
      .SBDATO3(dato[3]), .SBDATO2(dato[2]), .SBDATO1(dato[1]), .SBDATO0(dato[0]),
      .SBACKO(ack), .I2CIRQ(irq), .I2CWKUP(wkup),
      .SCLO(sclo), .SCLOE(scloe), .SDAO(sdao), .SDAOE(sdaoe));
   assign SCL = scloe ? sclo : 1'bz;
   assign SDA = sdaoe ? sdao : 1'bz;
   assign LED_R = ~(^dato); assign LED_G = ~ack; assign LED_B = ~(irq ^ wkup);
endmodule
"""

SPI = """module top(input clk, inout MOSI, inout MISO, inout SCK, inout SCSN,
           output LED_R, output LED_G, output LED_B);
   reg [7:0] addr = 0; reg stb = 0;
   always @(posedge clk) begin addr <= addr + 1'b1; stb <= ~stb; end
   wire [7:0] dato; wire ack, irq, wkup, so, soe, mo, moe, scko, sckoe;
   wire [3:0] mcsno, mcsnoe;
   SB_SPI #(.BUS_ADDR74("0b0000")) spi (
      .SBCLKI(clk), .SBRWI(1'b1), .SBSTBI(stb),
      .SBADRI7(addr[7]), .SBADRI6(addr[6]), .SBADRI5(addr[5]), .SBADRI4(addr[4]),
      .SBADRI3(addr[3]), .SBADRI2(addr[2]), .SBADRI1(addr[1]), .SBADRI0(addr[0]),
      .SBDATI7(1'b0), .SBDATI6(1'b0), .SBDATI5(1'b0), .SBDATI4(1'b0),
      .SBDATI3(1'b0), .SBDATI2(1'b0), .SBDATI1(1'b0), .SBDATI0(1'b0),
      .MI(MISO), .SI(MOSI), .SCKI(SCK), .SCSNI(SCSN),
      .SBDATO7(dato[7]), .SBDATO6(dato[6]), .SBDATO5(dato[5]), .SBDATO4(dato[4]),
      .SBDATO3(dato[3]), .SBDATO2(dato[2]), .SBDATO1(dato[1]), .SBDATO0(dato[0]),
      .SBACKO(ack), .SPIIRQ(irq), .SPIWKUP(wkup),
      .SO(so), .SOE(soe), .MO(mo), .MOE(moe),
      .SCKO(scko), .SCKOE(sckoe),
      .MCSNO0(mcsno[0]), .MCSNO1(mcsno[1]), .MCSNO2(mcsno[2]), .MCSNO3(mcsno[3]),
      .MCSNOE0(mcsnoe[0]), .MCSNOE1(mcsnoe[1]), .MCSNOE2(mcsnoe[2]),
      .MCSNOE3(mcsnoe[3]));
   assign MISO = soe ? so : 1'bz;  assign MOSI = moe ? mo : 1'bz;
   assign SCK = sckoe ? scko : 1'bz;  assign SCSN = mcsnoe[0] ? mcsno[0] : 1'bz;
   assign LED_R = ~(^dato ^ ^mcsno[3:1]); assign LED_G = ~(ack ^ ^mcsnoe[3:1]);
   assign LED_B = ~(irq ^ wkup);
endmodule
"""

LEDDA = """module top(input clk, output LED_R, output LED_G, output LED_B);
   reg [7:0] d = 0; reg [3:0] a = 0;
   always @(posedge clk) begin d <= d + 1'b1; a <= a + 1'b1; end
   wire p0, p1, p2, on;
   SB_LEDDA_IP ledda (
      .LEDDCS(1'b1), .LEDDCLK(clk),
      .LEDDDAT7(d[7]), .LEDDDAT6(d[6]), .LEDDDAT5(d[5]), .LEDDDAT4(d[4]),
      .LEDDDAT3(d[3]), .LEDDDAT2(d[2]), .LEDDDAT1(d[1]), .LEDDDAT0(d[0]),
      .LEDDADDR3(a[3]), .LEDDADDR2(a[2]), .LEDDADDR1(a[1]), .LEDDADDR0(a[0]),
      .LEDDDEN(1'b1), .LEDDEXE(1'b1),
      .PWMOUT0(p0), .PWMOUT1(p1), .PWMOUT2(p2), .LEDDON(on));
   assign LED_R = ~p0; assign LED_G = ~(p1 ^ p2); assign LED_B = ~on;
endmodule
"""

RGBA = """module top(input clk, output RGB0, output RGB1, output RGB2);
   reg [23:0] c = 0;
   always @(posedge clk) c <= c + 1'b1;
   SB_RGBA_DRV #(.CURRENT_MODE("0b1"), .RGB0_CURRENT("0b000001"),
                 .RGB1_CURRENT("0b000001"), .RGB2_CURRENT("0b000001")) rgba (
      .CURREN(1'b1), .RGBLEDEN(1'b1),
      .RGB0PWM(c[23]), .RGB1PWM(c[22]), .RGB2PWM(c[21]),
      .RGB0(RGB0), .RGB1(RGB1), .RGB2(RGB2));
endmodule
"""

DESIGNS = (
    ("i2c", I2C, "set_io clk 35\nset_io SCL 2\nset_io SDA 3\n" + LEDS),
    ("spi", SPI, "set_io clk 35\nset_io MOSI 2\nset_io MISO 3\nset_io SCK 4\n"
                 "set_io SCSN 6\n" + LEDS),
    ("ledda", LEDDA, "set_io clk 35\n" + LEDS),
    ("rgba", RGBA, "set_io clk 35\nset_io RGB0 39\nset_io RGB1 40\nset_io RGB2 41\n"),
)


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def build(name: str, verilog: str, pcf: str) -> Path:
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / f"{name}.v").write_text(verilog, encoding="utf-8")
    (BUILD / f"{name}.pcf").write_text(pcf, encoding="utf-8")
    subprocess.run(
        ["yosys", "-q", "-l", str(BUILD / f"{name}_yosys.log"),
         "-p", f"synth_ice40 -json {BUILD / f'{name}.json'}", str(BUILD / f"{name}.v")],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["nextpnr-ice40", "--up5k", "--package", "sg48",
         "--json", str(BUILD / f"{name}.json"), "--pcf", str(BUILD / f"{name}.pcf"),
         "--asc", str(BUILD / f"{name}.asc"), "--freq", "12",
         "--log", str(BUILD / f"{name}_pnr.log")],
        check=True, capture_output=True,
    )
    return BUILD / f"{name}.asc"


def survey(name: str, asc: Path) -> dict:
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(asc))
    graph = GlobalDriverGraph(ic, icebox)
    slf = sorted({s for group in ic.group_segments() for s in group if "slf_op" in s[2]})
    undriven = [
        sorted(group)
        for group in ic.group_segments()
        if not ({graph.driver_identity(s) for s in group} - {None})
    ]
    placement = re.search(
        r"constrained (SB_\w+) '\w+' to (\S+)",
        (BUILD / f"{name}_pnr.log").read_text(encoding="utf-8"),
    )
    return {
        "slf_op": slf,
        "undriven": undriven,
        "placement": placement.group(2) if placement else "?",
        "no_sb_io": "not creating SB_IO" in (BUILD / f"{name}_pnr.log").read_text(
            encoding="utf-8"
        ),
    }


def main() -> int:
    results = {}
    for name, verilog, pcf in DESIGNS:
        asc = build(name, verilog, pcf)
        results[name] = survey(name, asc)
        entry = results[name]
        print(f"\n=== {name} ({entry['placement']}) ===")
        print(f"  fabric endpoints (slf_op): {len(entry['slf_op'])}")
        for segment in entry["slf_op"][:6]:
            print(f"    {segment}")
        if len(entry["slf_op"]) > 6:
            print(f"    ... and {len(entry['slf_op']) - 6} more")
        print(f"  components with no driver at all: {len(entry['undriven'])}")

    print("\n=== verdicts: the database's endpoint set, exactly ===")
    icebox = load_icebox()
    for name, expected_count in (("i2c", 15), ("spi", 25), ("ledda", 4), ("rgba", 0)):
        cell = cell_ports(icebox, name)
        expected = db_endpoints(cell)
        measured = {(s[0], s[1], s[2]) for s in results[name]["slf_op"]}
        check(
            f"{name}: the database states {expected_count} fabric endpoints",
            len(expected) == expected_count, f"{len(expected)}",
        )
        # Both directions, and by coordinate.  Comparing the tiles an endpoint
        # falls in -- which is what this file did first -- passes with half of
        # them missing.
        check(
            f"{name}: the placed design reaches every one of them",
            not (expected - measured),
            f"{len(expected - measured)} unreached: {sorted(expected - measured)[:3]}",
        )
        check(
            f"{name}: and reaches nothing the database does not list",
            not (measured - expected),
            f"{len(measured - expected)} extra: {sorted(measured - expected)[:3]}",
        )

    print("\n=== enabling configuration, read from the built design ===")
    baseline = icebox.iceconfig()
    baseline.read_file(str(ROOT / "build" / "leds.asc"))
    for name in ("i2c", "spi", "rgba"):
        cell = cell_ports(icebox, name)
        enables = db_enable_bits(cell)
        active = icebox.iceconfig()
        active.read_file(str(BUILD / f"{name}.asc"))
        for port, (x, y, bit) in sorted(enables.items()):
            check(
                f"{name}: {port} at ({x},{y}) {bit} is set",
                ipconfig_bit(active, x, y, bit) == "1",
                f"read {ipconfig_bit(active, x, y, bit)!r}",
            )
            # Without this the check above would pass on a bit that is simply
            # always 1, and prove nothing about the IP being enabled.
            check(
                f"{name}: and clear in a design without the IP",
                ipconfig_bit(baseline, x, y, bit) == "0",
                f"read {ipconfig_bit(baseline, x, y, bit)!r}",
            )

    ledda_enables = db_enable_bits(cell_ports(icebox, "ledda"))
    check(
        "ledda: the database states no enabling bit at all",
        not ledda_enables, f"{sorted(ledda_enables)}",
    )
    print(
        "  => UNDETERMINED, not 'always on': with no configuration bit there is\n"
        "     no way to read whether LEDDA drives the fabric in a given design.\n"
        "     Whether to treat it as an unconditional source is a question about\n"
        "     the silicon, and this survey cannot answer it."
    )

    print("\n=== rgba: a negative, from three independent observations ===")
    rgba = results["rgba"]
    check(
        "rgba: nextpnr creates no SB_IO for its outputs",
        rgba["no_sb_io"],
        "the driver takes the pads; there is no IO block to source from",
    )
    check(
        "rgba: the placed design contributes no fabric endpoint",
        not rgba["slf_op"],
    )
    check(
        "rgba: and the database lists no fabric port for it either",
        not db_endpoints(cell_ports(icebox, "rgba")),
    )
    print(
        "  => rgba is a fabric sink and a package-pin driver.  Not applicable to\n"
        "     the driver graph; it should carry a negative regression, not an identity."
    )

    shared = {(s[0], s[1]) for s in results["i2c"]["slf_op"]} & {
        (s[0], s[1]) for s in results["ledda"]["slf_op"]
    }
    print(f"\n  note: i2c and ledda share ipcon tile(s) {sorted(shared)}, so an identity")
    print("        cannot be assigned by tile alone -- it must resolve the slf_op index")
    print("        to the owning IP.")

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: inventory complete for I2C, SPI, LEDDA and RGBA")
    print(
        "Undetermined and therefore not claimed either way: every other hard IP on "
        "the device, and the write paths of the blocks surveyed here."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regenerate the measurements the oscillator driver identity rests on.

`osc_check.py` verifies the combined fixture and the HFOSC named positive, but
three of the facts the identity is built on were, until this script existed,
recorded only in comments.  A claim that lives only in a comment cannot be
re-checked when the database or the toolchain changes, so each one is rebuilt
and asserted here:

  1. HFOSC alone sets `padin_glb_netwk 4`; LFOSC alone sets 5.  This is why the
     mapping is not taken from icebox's own comment, which annotates a
     different device's table.
  2. A `padin_glb_netwk` extra bit means an on-chip source.  Driving a global
     from package pin 23 -- the pad that shares padin index 4 -- sets no extra
     bit at all and puts the pad's own `io_0/D_IN_0` in the component as its
     driver.  Without this, a pad-driven global and an oscillator-driven one
     would be indistinguishable and the identity would risk false positives.
  3. `CLKHF_DIV` is encoded in `dsp1_tile (0,16)` as two IpConfig bits --
     `CBIT_3` (`B2[7]`) is the low bit and `CBIT_4` (`B5[7]`) the high one.
     An earlier revision of this project claimed the divider left no trace in
     the ASC at all.  That was wrong, and wrong for an instructive reason: the
     comparison enumerated io, logic, ipcon, ramb and ramt tiles and omitted
     `dsp_tiles`, so it could not see the only tile that changed.  Building all
     four divider values and diffing them is what this section now does.

Host-only; every design here is synthesised and placed, never programmed.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BUILD = ROOT / "build" / "osc_evidence"
sys.path.insert(0, str(HERE))

from iceutil import load_icebox  # noqa: E402

failures: list[str] = []

PCF_LEDS = """set_io LED_R 40
set_io LED_G 41
set_io LED_B 39
"""

HFOSC_ONLY = """module top(output LED_R, output LED_G, output LED_B);
    wire clk_hf;
    SB_HFOSC #(.CLKHF_DIV("0b10")) hfosc (
        .CLKHFPU(1'b1), .CLKHFEN(1'b1), .CLKHF(clk_hf));
    reg [23:0] fast = 0;
    always @(posedge clk_hf) fast <= fast + 1'b1;
    assign LED_R = ~fast[23];
    assign LED_G = ~fast[22];
    assign LED_B = ~fast[21];
endmodule
"""

LFOSC_ONLY = """module top(output LED_R, output LED_G, output LED_B);
    wire clk_lf;
    SB_LFOSC lfosc (.CLKLFPU(1'b1), .CLKLFEN(1'b1), .CLKLF(clk_lf));
    reg [7:0] slow = 0;
    always @(posedge clk_lf) slow <= slow + 1'b1;
    assign LED_R = ~slow[7];
    assign LED_G = ~slow[6];
    assign LED_B = ~slow[5];
endmodule
"""

PAD_CLOCK = """module top(input clk_pin23, output LED_R, output LED_G, output LED_B);
    reg [23:0] counter = 0;
    always @(posedge clk_pin23) counter <= counter + 1'b1;
    assign LED_R = ~counter[23];
    assign LED_G = ~counter[22];
    assign LED_B = ~counter[21];
endmodule
"""

PAD_CLOCK_PCF = "set_io clk_pin23 23\n" + PCF_LEDS


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def build(name: str, verilog: str, pcf: str, div: str | None = None) -> Path:
    """Synthesise and place one variant, returning its ASC path."""
    BUILD.mkdir(parents=True, exist_ok=True)
    source = BUILD / f"{name}.v"
    if div is not None:
        verilog = verilog.replace('.CLKHF_DIV("0b10")', f'.CLKHF_DIV("{div}")')
    source.write_text(verilog, encoding="utf-8")
    (BUILD / f"{name}.pcf").write_text(pcf, encoding="utf-8")
    subprocess.run(
        ["yosys", "-q", "-l", str(BUILD / f"{name}_yosys.log"),
         "-p", f"synth_ice40 -json {BUILD / f'{name}.json'}", str(source)],
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


def extra_bits(path: Path) -> set:
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(path))
    return {ic.lookup_extra_bit(bit) for bit in ic.extra_bits}


def main() -> int:
    print("=== 1. which padin index belongs to which oscillator ===")
    hf = extra_bits(build("hfosc_only", HFOSC_ONLY, PCF_LEDS))
    lf = extra_bits(build("lfosc_only", LFOSC_ONLY, PCF_LEDS))
    print(f"  HFOSC alone: {sorted(hf)}")
    print(f"  LFOSC alone: {sorted(lf)}")
    check("HFOSC alone sets exactly padin_glb_netwk 4", hf == {("padin_glb_netwk", "4")})
    check("LFOSC alone sets exactly padin_glb_netwk 5", lf == {("padin_glb_netwk", "5")})

    print("\n=== 2. a padin_glb_netwk bit means an on-chip source ===")
    pad_asc = build("pad_clock", PAD_CLOCK, PAD_CLOCK_PCF)
    pad_extra = extra_bits(pad_asc)
    print(f"  pin 23 driving a global: extra bits {sorted(pad_extra) or '(none)'}")
    check(
        "a pad-driven global sets no padin_glb_netwk bit",
        not pad_extra,
        "so the bit cannot be produced by the pad that shares padin index 4",
    )
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(pad_asc))
    from exhaustive import GlobalDriverGraph  # noqa: PLC0415

    graph = GlobalDriverGraph(ic, icebox)
    pad_driven = []
    for segments in ic.group_segments():
        if not any("glb_netwk" in segment[2] for segment in segments):
            continue
        identities = {graph.driver_identity(segment) for segment in segments} - {None}
        pad_driven.append(sorted(identities))
    print(f"  drivers of the pad-driven global: {pad_driven}")
    check(
        "the pad itself is recognised as that global's driver",
        any(
            any(identity[0] == "io" and identity[1:3] == (19, 31) for identity in group)
            for group in pad_driven
        ),
        f"{pad_driven}",
    )
    check(
        "and no oscillator identity is claimed for it",
        not graph.oscillator_sources,
        f"{graph.oscillator_sources}",
    )

    print("\n=== 3. how CLKHF_DIV is encoded ===")
    configs = {}
    for value in ("0b00", "0b01", "0b10", "0b11"):
        asc = build(f"hfosc_div{value[2:]}", HFOSC_ONLY, PCF_LEDS, div=value)
        ic_div = load_icebox().iceconfig()
        ic_div.read_file(str(asc))
        configs[value] = ic_div
    base = configs["0b00"]
    observed = {}
    for value, ic_div in configs.items():
        names = set()
        for index, (base_tiles, tiles) in enumerate(
            zip(base.dsp_tiles, ic_div.dsp_tiles)
        ):
            for xy in base_tiles:
                for row in range(len(base_tiles[xy])):
                    for column in range(len(base_tiles[xy][row])):
                        if base_tiles[xy][row][column] == tiles[xy][row][column]:
                            continue
                        name = next(
                            (
                                entry[2]
                                for entry in ic_div.tile_db(*xy)
                                if f"B{row}[{column}]" in entry[0]
                                and entry[1] == "IpConfig"
                            ),
                            "?",
                        )
                        names.add((index, xy, name))
        observed[value] = names
        print(f"  {value}: {sorted(names) or '(baseline)'}")
    low = (1, (0, 16), "CBIT_3")
    high = (1, (0, 16), "CBIT_4")
    check("CLKHF_DIV=0b00 sets neither divider bit", observed["0b00"] == set())
    check("CLKHF_DIV=0b01 sets only the low bit (dsp1 (0,16) CBIT_3)",
          observed["0b01"] == {low})
    check("CLKHF_DIV=0b10 sets only the high bit (dsp1 (0,16) CBIT_4)",
          observed["0b10"] == {high})
    check("CLKHF_DIV=0b11 sets both", observed["0b11"] == {low, high})

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: every measurement the oscillator identity rests on regenerates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

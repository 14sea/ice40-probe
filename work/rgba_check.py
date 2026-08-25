#!/usr/bin/env python3
"""The negative regression for SB_RGBA_DRV.

Host-only.  Sixth and last of the surveyed blocks, and the only one that gets
no driver identity for a reason other than "not modelled yet": the RGB driver
has no output that enters the programmable fabric.  It drives three package
pads and reads five fabric inputs, so it is a sink and a pin driver -- not
applicable to the driver graph rather than missing from it.

A negative is only ever as good as the enumeration behind it, and this project
has produced a clean-looking negative from an incomplete enumeration three
times.  So this file does not simply report "no slf_op found":

  * all twenty-eight of the block's database ports are classified -- five
    fabric inputs, three package pads, twenty configuration bits -- and the
    classification has to be exhaustive.  A port of an unrecognised shape
    fails the check rather than being passed over;
  * the same endpoint extraction is run against I2C, SPI and LEDDA, where it
    finds fifteen, twenty-five and four.  A search that returns zero because
    it is broken would return zero for those too;
  * the block is really placed and really enabled, read back from the built
    bitstream.  "No fabric output" is trivially true of a design that contains
    no RGB driver, and that vacuous version of this check is what the
    non-vacuity section exists to rule out;
  * the model is shown to annotate a real input pad in this very design (the
    clock), so the silence on the RGBA pads is a property of those pads and
    not of a model that cannot see IO at all.

The contrast with LEDDA is the point of the wording "not applicable": LEDDA
has four fabric outputs and no enabling bit, so whether it drives them is not
a configuration fact and its state is UNDETERMINED.  RGBA is the mirror image
-- an enabling bit and no fabric output -- and that is a determined negative.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from exhaustive import (  # noqa: E402
    GlobalDriverGraph,
    enable_gated_fabric_endpoints,
    ipconfig_bit,
)
from iceutil import load_icebox  # noqa: E402
from oracle import conflicting_nets, driver_identity  # noqa: E402

ASC = Path(sys.argv[1] if len(sys.argv) > 1 else "build/rgba.asc")
LEDS_ASC = ASC.with_name("leds.asc")
I2C_ASC = ASC.with_name("i2c.asc")
SPI_ASC = ASC.with_name("spi.asc")
PNR_LOG = ASC.with_name("rgba_pnr.log")

RGBA = ("RGBA_DRV", (0, 30, 0))
PADS = ((4, 31, 0), (5, 31, 0), (6, 31, 0))
PAD_PINS = ("39", "40", "41")

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}{(' -- ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def load(path: Path):
    icebox = load_icebox()
    ic = icebox.iceconfig()
    ic.read_file(str(path))
    return icebox, ic


def cell(icebox, kind, placement=None):
    for key, ports in icebox.extra_cells_db["5k"].items():
        if key[0] == kind and (placement is None or key[1] == placement):
            return ports
    raise KeyError(f"{kind} {placement} is not in extra_cells_db['5k']")


def classify(port: str, value):
    """Which of the three shapes a database port has, or None if unrecognised."""
    if isinstance(value, tuple) and len(value) == 3:
        x, y, third = value
        if isinstance(third, int):
            return "package pad"
        if str(third).startswith("slf_op"):
            return "fabric output"
        if re.fullmatch(r"lutff_\d+/in_\d+", str(third)) or str(third) == "clk":
            return "fabric input"
        if str(third).startswith("CBIT_") or "delay" in str(third) or str(
            third
        ).startswith("cbit"):
            return "configuration bit"
    return None


def slf_op_segments(ic) -> set:
    return {
        segment
        for group in ic.group_segments()
        for segment in group
        if "slf_op" in segment[2]
    }


def main() -> int:
    icebox, ic = load(ASC)
    ports = cell(icebox, "RGBA_DRV", RGBA[1])

    print("=== the block is really there, so the negative is not vacuous ===")
    log = PNR_LOG.read_text(encoding="utf-8") if PNR_LOG.exists() else ""
    placed = re.search(r"constrained SB_RGBA_DRV '\w+' to (\S+)", log)
    check(
        "nextpnr placed an SB_RGBA_DRV",
        placed is not None and placed.group(1) == "X0/Y30/rgba_drv_0",
        placed.group(1) if placed else "no placement line in the placer log",
    )
    enable = ports["RGBA_DRV_EN"]
    check(
        "RGBA_DRV_EN is set in the built bitstream",
        ipconfig_bit(ic, enable[0], enable[1], enable[2]) == "1",
        f"{enable} reads {ipconfig_bit(ic, enable[0], enable[1], enable[2])!r}",
    )
    _leds_icebox, ic_leds = load(LEDS_ASC)
    check(
        "and clear in a design without the block",
        ipconfig_bit(ic_leds, enable[0], enable[1], enable[2]) == "0",
        "otherwise the bit would say nothing about this block",
    )
    mode = ports["CURRENT_MODE"]
    check(
        "CURRENT_MODE reads back the value the fixture asked for",
        ipconfig_bit(ic, mode[0], mode[1], mode[2]) == "1",
        'the fixture sets CURRENT_MODE("0b1")',
    )
    current = [
        ipconfig_bit(ic, *ports[f"RGB0_CURRENT_{index}"]) for index in range(6)
    ]
    check(
        'RGB0_CURRENT("0b000001") lands as exactly one of its six bits',
        current.count("1") == 1,
        f"read {''.join(str(value) for value in current)} "
        f"(bit {current.index('1')} of RGB0_CURRENT_0..5)",
    )

    print("\n=== every one of the twenty-eight ports is accounted for ===")
    classified = {}
    for port, value in sorted(ports.items()):
        classified.setdefault(classify(port, value), []).append(port)
    check(
        "no port has an unrecognised shape",
        None not in classified,
        f"{classified.get(None, [])}",
    )
    check(
        "five fabric inputs",
        sorted(classified.get("fabric input", []))
        == ["CURREN", "RGB0PWM", "RGB1PWM", "RGB2PWM", "RGBLEDEN"],
        f"{sorted(classified.get('fabric input', []))}",
    )
    check(
        "three package pads",
        sorted(classified.get("package pad", [])) == ["RGB0", "RGB1", "RGB2"],
        f"{sorted(classified.get('package pad', []))}",
    )
    check(
        "twenty configuration bits",
        len(classified.get("configuration bit", [])) == 20,
        f"{len(classified.get('configuration bit', []))}",
    )
    check(
        "and zero fabric outputs",
        not classified.get("fabric output"),
        f"{classified.get('fabric output', [])}",
    )
    check(
        "the three classes account for all twenty-eight ports",
        sum(len(names) for names in classified.values()) == 28 and len(ports) == 28,
        f"{sum(len(names) for names in classified.values())} of {len(ports)}",
    )

    print("\n=== the same search finds the other blocks' outputs ===")
    # A search that returns zero because it is broken returns zero everywhere.
    for kind, placement, expected in (
        ("I2C", (0, 31, 0), 15),
        ("SPI", (0, 0, 0), 25),
        ("LEDDA_IP", (0, 31, 2), 4),
    ):
        found = len(enable_gated_fabric_endpoints(cell(icebox, kind, placement)))
        check(
            f"{kind} at {placement}: {expected} fabric endpoints",
            found == expected,
            f"{found}",
        )
    check(
        "RGBA: zero, from the same extraction",
        not enable_gated_fabric_endpoints(ports),
        f"{sorted(enable_gated_fabric_endpoints(ports))}",
    )
    _i2c_icebox, ic_i2c = load(I2C_ASC)
    _spi_icebox, ic_spi = load(SPI_ASC)
    check(
        "and in the placed designs: 30 for i2c, 50 for spi, 0 for rgba",
        len(slf_op_segments(ic_i2c)) == 30
        and len(slf_op_segments(ic_spi)) == 50
        and not slf_op_segments(ic),
        f"{len(slf_op_segments(ic_i2c))}, {len(slf_op_segments(ic_spi))}, "
        f"{len(slf_op_segments(ic))}",
    )

    print("\n=== the three pads are the block's own, and drive nothing inward ===")
    pinloc = {
        str(entry[0]): (entry[1], entry[2], entry[3])
        for entry in icebox.pinloc_db["5k-sg48"]
    }
    check(
        "the database's pad triples are package pins 39, 40 and 41",
        tuple(pinloc[pin] for pin in PAD_PINS) == PADS,
        f"{[pinloc[pin] for pin in PAD_PINS]} vs {list(PADS)}",
    )
    check(
        "nextpnr creates no SB_IO for any of the three",
        log.count("not creating SB_IO") == 3,
        f"{log.count('not creating SB_IO')} such lines",
    )
    graph = GlobalDriverGraph(ic, icebox)
    pad_tiles = {(x, y) for x, y, _block in PADS}
    pad_segments = {
        segment
        for group in ic.group_segments()
        for segment in group
        if (segment[0], segment[1]) in pad_tiles
    }
    check(
        "their tiles carry nothing but the clock global",
        {segment[2] for segment in pad_segments} == {"glb_netwk_4"},
        f"{sorted({segment[2] for segment in pad_segments})}",
    )
    leds_pad_segments = {
        segment
        for group in ic_leds.group_segments()
        for segment in group
        if (segment[0], segment[1]) in pad_tiles
    }
    check(
        "while the same tiles carry IO structure when the pins are ordinary IO",
        any("io_" in segment[2] for segment in leds_pad_segments)
        and len(leds_pad_segments) > len(pad_segments),
        f"leds: {len(leds_pad_segments)} segments, rgba: {len(pad_segments)}",
    )
    check(
        "no pad segment resolves to a driver",
        all(graph.driver_identity(segment) is None for segment in pad_segments),
    )
    # And the model is not simply blind to pads: the clock input in this very
    # design gets an IO identity.
    check(
        "the clock input pad in this same design does get one",
        graph.driver_identity((12, 31, "io_1/D_IN_0")) == ("io", 12, 31, "io_1/D_IN_0"),
        "so the silence above is about these pads, not about IO in general",
    )

    print("\n=== no hard-IP identity is created anywhere in this design ===")
    identities = {
        graph.driver_identity(segment)
        for group in ic.group_segments()
        for segment in group
    }
    identities.discard(None)
    check(
        "only LUT and IO sources exist here",
        {identity[0] for identity in identities} == {"lutff", "io"},
        f"{sorted({identity[0] for identity in identities})}",
    )
    check(
        "the enabled RGB driver contributes none of them",
        not any(identity[0] == "rgba" for identity in identities),
        "there is no rgba identity to contribute, by construction",
    )
    check(
        "an RGBA pad segment resolves to None in the oracle too",
        driver_identity(ic, icebox, (4, 31, "glb_netwk_4")) is None,
    )
    check("model baseline has no multi-driver net", graph.base_multi_driver_nets == 0)
    check("oracle baseline has no conflicting net", conflicting_nets(ic, icebox) == 0)

    print("\n=== not applicable, which is not the same as undetermined ===")
    ledda = cell(icebox, "LEDDA_IP", (0, 31, 2))
    ledda_enables = [port for port in ledda if "ENABLE" in port or port.endswith("_EN")]
    check(
        "RGBA has an enabling bit and no fabric output",
        "RGBA_DRV_EN" in ports and not enable_gated_fabric_endpoints(ports),
        "its state is a configuration fact; there is simply nothing to drive",
    )
    check(
        "LEDDA is the mirror image: four fabric outputs and no enabling bit",
        len(enable_gated_fabric_endpoints(ledda)) == 4 and not ledda_enables,
        "so LEDDA is undetermined, while RGBA is a determined negative",
    )

    print()
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed")
        for label in failures:
            print(f"  - {label}")
        return 1
    print("PASS: RGBA is a fabric sink and a pin driver, on an exhaustive port count")
    print(
        "Coverage boundary: this says the published configuration gives "
        "SB_RGBA_DRV no path into the fabric, so it cannot be a source in this "
        "graph.  It says nothing about the block's analogue behaviour, and it "
        "is a statement about IceStorm's database, which no measurement here "
        "has checked against silicon.  LEDDA remains undetermined for the "
        "opposite reason: outputs, but no configuration bit to gate them."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

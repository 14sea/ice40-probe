#!/usr/bin/env python3
"""Shared helpers for the iCE40 host-side analysis scripts."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import warnings


LUT_BITNUMS = frozenset((4, 14, 15, 5, 6, 16, 17, 7, 3, 13, 12, 2, 1, 11, 10, 0))
SEQ_BITNUMS = frozenset((8, 9, 18, 19))
ROWS = 16
COLS = 54


def load_icebox():
    """Import IceStorm's Python module without assuming one installation path."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return importlib.import_module("icebox")
    except ModuleNotFoundError:
        pass

    candidates = []
    configured = os.environ.get("ICESTORM_PYTHON")
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        (
            Path("/usr/share/fpga-icestorm/python"),
            Path("/usr/local/share/fpga-icestorm/python"),
        )
    )
    for candidate in candidates:
        if (candidate / "icebox.py").is_file():
            sys.path.insert(0, str(candidate))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                return importlib.import_module("icebox")
    raise RuntimeError(
        "cannot import IceStorm's icebox module; set ICESTORM_PYTHON to its directory"
    )


def positive_bit_name(name: str) -> str:
    return name[1:] if name.startswith("!") else name


def physical_bitnum(row: int, column: int) -> int | None:
    if not 36 <= column < 46:
        return None
    return (column - 36) + 10 * (row % 2)


def is_lut_init_position(row: int, column: int) -> bool:
    return physical_bitnum(row, column) in LUT_BITNUMS


def is_lc_seq_position(row: int, column: int) -> bool:
    return physical_bitnum(row, column) in SEQ_BITNUMS


def signed_tile_bits(tile: list[str]) -> set[str]:
    return {
        ("" if value == "1" else "!") + f"B{row}[{column}]"
        for row, line in enumerate(tile)
        for column, value in enumerate(line)
    }


# --- canonical configuration-tile enumeration --------------------------------
#
# Two separate defects in this project came from a hand-written tile-type list
# that silently omitted one entry.  The global driver check was gated on a local
# condition and never saw the cross-tile class; and a diff that enumerated io,
# logic, ipcon, ramb and ramt tiles concluded that CLKHF_DIV left no trace in
# the ASC, when it is encoded in `dsp_tiles` -- the one collection the list
# omitted.  Both produced a clean-looking negative.
#
# So: nothing here hand-writes that list any more.  Scripts iterate through
# `configuration_tiles`, and `assert_tile_coverage` fails loudly if an iceconfig
# ever exposes a collection that nobody has classified.

TILE_COLLECTIONS = (
    "io_tiles",
    "logic_tiles",
    "ramb_tiles",
    "ramt_tiles",
    "ipcon_tiles",
    "dsp_tiles",          # a list of four maps, not a single map
)

# Configuration that is real but is not a tile map.  Named explicitly so that
# "not a tile" is a decision on the record rather than an oversight.
NON_TILE_CONFIGURATION = {
    "extra_bits": "padin_glb_netwk and friends; used by the PLL and oscillator "
                  "driver identities",
    "ram_data": "block RAM initial contents, not routing or driver state",
    "warmboot": "boot-image selection, not fabric configuration",
}

# Attributes that carry no configuration at all.
NON_CONFIGURATION = ("device", "max_x", "max_y", "symbols")


def _is_tile_map(value) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(isinstance(key, tuple) and len(key) == 2 for key in value)
    )


def configuration_tiles(ic):
    """Yield (collection_name, (x, y), tile) for every configuration tile."""
    for name in TILE_COLLECTIONS:
        value = getattr(ic, name)
        if isinstance(value, list):
            for index, mapping in enumerate(value):
                for coordinate, tile in mapping.items():
                    yield f"{name}[{index}]", coordinate, tile
        else:
            for coordinate, tile in value.items():
                yield name, coordinate, tile


def assert_tile_coverage(ic) -> None:
    """Raise if the iceconfig exposes a tile collection nobody has classified."""
    classified = set(TILE_COLLECTIONS) | set(NON_TILE_CONFIGURATION) | set(NON_CONFIGURATION)
    unclassified = []
    for name, value in vars(ic).items():
        if name in classified:
            continue
        if _is_tile_map(value) or (
            isinstance(value, list) and value and all(
                _is_tile_map(item) or item == {} for item in value
            )
        ):
            unclassified.append(name)
    if unclassified:
        raise AssertionError(
            "iceconfig exposes tile collections this module has not classified: "
            f"{sorted(unclassified)}.  Add them to TILE_COLLECTIONS or to "
            "NON_TILE_CONFIGURATION with a reason; do not let them be skipped "
            "silently."
        )

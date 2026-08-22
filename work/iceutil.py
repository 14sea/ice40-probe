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

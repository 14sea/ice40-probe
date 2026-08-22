#!/usr/bin/env python3
"""Decode an ASC file and optionally remove redundant port redeclarations."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("asc", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--simulation", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    result = subprocess.run(
        ["icebox_vlog", str(args.asc)],
        check=True,
        capture_output=True,
        text=True,
    )
    source = result.stdout
    if args.simulation:
        module = re.search(r"module\s+\w+\s*\((.*?)\);", source, re.DOTALL)
        if not module:
            raise ValueError("cannot parse decoded module ports")
        ports = set(re.findall(r"(?:input|output|inout)\s+(\w+)", module.group(1)))
        output_ports = set(re.findall(r"output\s+(\w+)", module.group(1)))
        port_reg_initializers = {}
        for match in re.finditer(
            r"^reg\s+(\w+)(?:\s*=\s*([^;]+))?;\s*$", source, re.MULTILINE
        ):
            if match.group(1) in output_ports:
                port_reg_initializers[match.group(1)] = match.group(2)

        header = module.group(0)
        for port in port_reg_initializers:
            header = re.sub(
                rf"\boutput\s+{re.escape(port)}\b",
                f"output reg {port}",
                header,
            )
        source = source[: module.start()] + header + source[module.end() :]

        normalized = []
        for line in source.splitlines():
            if any(re.fullmatch(rf"wire\s+{re.escape(port)};", line) for port in ports):
                continue
            reg_match = re.fullmatch(r"reg\s+(\w+)(?:\s*=\s*([^;]+))?;", line)
            if reg_match and reg_match.group(1) in port_reg_initializers:
                initializer = reg_match.group(2)
                if initializer is not None:
                    normalized.append(
                        f"initial {reg_match.group(1)} = {initializer};"
                    )
                continue
            normalized.append(line)
        source = "\n".join(normalized) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

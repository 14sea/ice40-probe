#!/usr/bin/env python3
"""Generate a traceable evidence manifest.

The sweep result files are large and regenerable, so they are not tracked in
git.  That is only acceptable if what they contain can be attested to: this
script records, for every result file, the SHA-256 of the file itself, the
hashes it was produced against (ASC, IceStorm database, both model sources),
the counts, the coordinates of every oracle positive, and the run information.

It also re-runs the three hard-IP fixture checks so the manifest states their
outcome at generation time rather than quoting a past run, and hashes the
checked-in fixture ASCs that `verify-repro` compares against.

Writes `docs/evidence_manifest.json` and `docs/evidence_manifest.md`.

With `--check` it writes nothing and instead verifies that the tracked manifest
is still current.  Only the sections derived from tracked files can be checked
that way -- the hashes of `work/*.py` and of the checked-in fixture ASCs -- so
those are what the gate covers.  The rest (tool versions, fixture re-runs, sweep
results) depends on the machine and on untracked result files, and a fresh clone
could not reproduce it.  That is enough to catch the failure this gate exists
for: editing a model source, or adding one, and leaving the manifest behind.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

RESULTS = ROOT / "results"
BUILD = ROOT / "build"
DOCS = ROOT / "docs"

FIXTURE_CHECKS = (
    ("pll", "pll_check.py", "pll.asc"),
    ("spram", "spram_check.py", "spram.asc"),
    ("oscillator", "osc_check.py", "osc.asc"),
    ("i2c", "i2c_check.py", "i2c.asc"),
)

TRACKED_ASCS = (
    "leds.asc",
    "dense.asc",
    "leds_mut2.asc",
    "leds_mut3.asc",
    "pll.asc",
    "pll_selector.asc",
    "spram.asc",
    "osc.asc",
    "osc_selector.asc",
    "osc_fabric_selector.asc",
    "i2c.asc",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_result(path: Path) -> dict:
    header = summary = None
    coordinates = set()
    positives = []
    disagreements = []
    malformed = duplicates = 0
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
            summary = record
            continue
        key = (record["x"], record["y"], record["row"], record["column"])
        if key in coordinates:
            duplicates += 1
        coordinates.add(key)
        if record["oracle"]:
            positives.append(
                {
                    "tile": [record["x"], record["y"]],
                    "bit": f"B{record['row']}[{record['column']}]",
                    "conflict_net_delta": record["oracle_conflict_nets"],
                }
            )
        if not record["agree"]:
            disagreements.append(key)
    return {
        "file": path.name,
        "file_sha256": sha256(path),
        "file_bytes": path.stat().st_size,
        "complete": summary is not None,
        "header": header,
        "summary": summary,
        "coordinates_checked": len(coordinates),
        "duplicate_records": duplicates,
        "malformed_lines": malformed,
        "oracle_positives": len(positives),
        "positive_coordinates": sorted(
            positives, key=lambda item: (item["tile"], item["bit"])
        ),
        "model_oracle_disagreements": len(disagreements),
    }


def tree_sections() -> dict:
    """The manifest sections that depend only on tracked files.

    Enumerated, not hand-listed.  A hand-written list is precisely how this
    project twice lost track of something it should have covered.
    """
    sections = {"model_sources": {}, "tracked_ascs": {}}
    for source in sorted(HERE.glob("*.py")):
        sections["model_sources"][source.name] = sha256(source)
    for asc in TRACKED_ASCS:
        path = HERE / asc
        if path.exists():
            sections["tracked_ascs"][asc] = sha256(path)
    return sections


def compare(recorded: dict, markdown: str, current: dict) -> list:
    """Every way the recorded manifest can fail to describe the current tree."""
    problems = []
    for section, entries in current.items():
        was = recorded.get(section) or {}
        for name in sorted(set(entries) | set(was)):
            if name not in was:
                problems.append(f"{section}: `work/{name}` is not recorded at all")
            elif name not in entries:
                problems.append(f"{section}: `work/{name}` is recorded but no longer exists")
            elif was[name] != entries[name]:
                problems.append(
                    f"{section}: `work/{name}` changed since the manifest was written\n"
                    f"      recorded {was[name]}\n      current  {entries[name]}"
                )
            elif f"- `work/{name}`: `{entries[name]}`" not in markdown:
                problems.append(
                    f"{section}: `work/{name}` matches the JSON but the markdown "
                    f"does not list that hash"
                )
    return problems


def self_test() -> int:
    """Prove the gate fires.  A guard that has never failed proves nothing.

    Each case is one way the manifest went stale in real life on this project:
    a model source was added and never recorded, and two were edited after the
    manifest was written.  The third case is the one a JSON-only check misses --
    the markdown that people actually read drifting away from the JSON.
    """
    current = {"model_sources": {"a.py": "aaa", "b.py": "bbb"}, "tracked_ascs": {}}
    markdown = "- `work/a.py`: `aaa`\n- `work/b.py`: `bbb`\n"
    failures = []

    def case(label: str, recorded: dict, text: str, expect: str) -> None:
        problems = compare(recorded, text, current)
        hit = any(expect in problem for problem in problems)
        print(f"  [{'PASS' if hit else 'FAIL'}] {label}")
        if not hit:
            failures.append(f"{label}: expected {expect!r}, got {problems}")

    case(
        "an unrecorded source is caught",
        {"model_sources": {"a.py": "aaa"}}, markdown,
        "`work/b.py` is not recorded at all",
    )
    case(
        "a changed source is caught",
        {"model_sources": {"a.py": "aaa", "b.py": "stale"}}, markdown,
        "`work/b.py` changed since the manifest was written",
    )
    case(
        "a source recorded but deleted is caught",
        {"model_sources": {"a.py": "aaa", "b.py": "bbb", "gone.py": "ggg"}}, markdown,
        "`work/gone.py` is recorded but no longer exists",
    )
    case(
        "markdown drifting from the JSON is caught",
        {"model_sources": {"a.py": "aaa", "b.py": "bbb"}}, "- `work/a.py`: `aaa`\n",
        "the markdown does not list that hash",
    )

    matching = compare({"model_sources": {"a.py": "aaa", "b.py": "bbb"}}, markdown, current)
    ok = matching == []
    print(f"  [{'PASS' if ok else 'FAIL'}] a matching manifest raises nothing")
    if not ok:
        failures.append(f"false positive: {matching}")

    if failures:
        print(f"FAIL: the gate does not fire in {len(failures)} case(s)")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("PASS: the freshness gate fires on every way the manifest can go stale")
    return 0


def check() -> int:
    """Fail if the tracked manifest no longer describes the tracked tree."""
    json_path = DOCS / "evidence_manifest.json"
    md_path = DOCS / "evidence_manifest.md"
    if not json_path.exists():
        print(f"FAIL: {json_path} is missing; run `make manifest`")
        return 1
    recorded = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    current = tree_sections()
    problems = compare(recorded, markdown, current)

    for label, count in (
        ("model sources", len(current["model_sources"])),
        ("tracked ASCs", len(current["tracked_ascs"])),
    ):
        print(f"  {count} {label} enumerated from the tree")
    if problems:
        print(f"\nFAIL: the manifest is stale in {len(problems)} place(s):")
        for problem in problems:
            print(f"  - {problem}")
        print("\n  Run `make manifest` and commit the result.")
        return 1
    print("PASS: the tracked manifest matches the tracked tree")
    return 0


def run_fixture_check(script: str, asc: str) -> dict:
    target = BUILD / asc
    if not target.exists():
        return {"script": script, "status": "skipped", "reason": f"{target} missing"}
    completed = subprocess.run(
        [sys.executable, str(HERE / script), str(target)],
        capture_output=True,
        text=True,
    )
    named = []
    for match in re.finditer(
        r"^(\w[\w ]*positive): tile=\((\d+),(\d+)\) bit=(B\d+\[\d+\])$",
        completed.stdout,
        re.MULTILINE,
    ):
        named.append(
            {
                "name": match.group(1),
                "tile": [int(match.group(2)), int(match.group(3))],
                "bit": match.group(4),
            }
        )
    failed = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().startswith("[FAIL]")
    ]
    return {
        "script": script,
        "asc": asc,
        "asc_sha256": sha256(target),
        "status": "pass" if completed.returncode == 0 else "fail",
        "named_positives": named,
        "failed_checks": failed,
    }


def main() -> int:
    manifest: dict = {"tool_versions": {}, "fixtures": [], "sweeps": [], "tracked_ascs": {}}

    for name, command in (
        ("yosys", ["yosys", "-V"]),
        ("nextpnr-ice40", ["nextpnr-ice40", "--version"]),
        ("iverilog", ["iverilog", "-V"]),
        ("python", [sys.executable, "--version"]),
    ):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            manifest["tool_versions"][name] = (result.stdout or result.stderr).strip().splitlines()[0]
        except Exception as error:  # noqa: BLE001
            manifest["tool_versions"][name] = f"unavailable: {error}"
    try:
        manifest["tool_versions"]["fpga-icestorm"] = subprocess.run(
            ["dpkg-query", "-W", "-f=${Version}", "fpga-icestorm"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        manifest["tool_versions"]["fpga-icestorm"] = "unknown"

    manifest.update(tree_sections())

    for name, script, asc in FIXTURE_CHECKS:
        entry = run_fixture_check(script, asc)
        entry["fixture"] = name
        manifest["fixtures"].append(entry)

    for path in sorted(RESULTS.glob("*.jsonl")):
        manifest["sweeps"].append(read_result(path))

    (DOCS / "evidence_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# Evidence manifest",
        "",
        "Generated by `python3 work/manifest.py`.  The sweep JSONL files are large",
        "and regenerable, so they are not tracked in git; this manifest is what makes",
        "their contents attestable.  Every number below is computed from the files at",
        "generation time, and the fixture rows come from re-running the checks, not",
        "from quoting an earlier run.",
        "",
        "## Toolchain",
        "",
    ]
    for name, version in manifest["tool_versions"].items():
        lines.append(f"- `{name}`: {version}")
    lines += ["", "## Model sources", ""]
    for name, digest in manifest["model_sources"].items():
        lines.append(f"- `work/{name}`: `{digest}`")

    lines += ["", "## Hard-IP fixtures", ""]
    for entry in manifest["fixtures"]:
        if entry.get("status") == "skipped":
            lines.append(f"- **{entry['fixture']}**: skipped ({entry.get('reason')})")
            continue
        lines.append(
            f"- **{entry['fixture']}** ({entry['asc']}, `{entry['asc_sha256'][:16]}…`): "
            f"{entry['status'].upper()}"
        )
        for positive in entry["named_positives"]:
            lines.append(
                f"  - {positive['name']}: tile ({positive['tile'][0]},"
                f"{positive['tile'][1]}) bit {positive['bit']}"
            )
        for failure in entry["failed_checks"]:
            lines.append(f"  - {failure}")

    lines += ["", "## Sweeps", ""]
    for sweep in manifest["sweeps"]:
        header = sweep["header"] or {}
        summary = sweep["summary"] or {}
        state = "complete" if sweep["complete"] else "**in progress**"
        lines += [
            f"### `{sweep['file']}` ({state})",
            "",
            f"- file SHA-256: `{sweep['file_sha256']}`",
            f"- size: {sweep['file_bytes']:,} bytes",
            f"- ASC: `{header.get('asc')}` `{header.get('asc_sha256')}`",
            f"- IceStorm module: `{header.get('icebox_sha256')}` "
            f"(package {header.get('icestorm_package')})",
            f"- model sources at run time: oracle `{header.get('oracle_sha256')}`, "
            f"exhaustive `{header.get('exhaustive_sha256')}`",
            f"- flip class: {header.get('flip_class')}, targets: {header.get('targets')}",
            f"- coordinates checked: {sweep['coordinates_checked']}, "
            f"duplicates: {sweep['duplicate_records']}, "
            f"malformed: {sweep['malformed_lines']}",
            f"- oracle positives: {sweep['oracle_positives']}, "
            f"model/oracle disagreements: {sweep['model_oracle_disagreements']}",
        ]
        if summary:
            lines.append(
                f"- run: {summary.get('workers')} workers, "
                f"{summary.get('elapsed_seconds', 0) / 60:.1f} min"
            )
        if sweep["positive_coordinates"]:
            lines += ["- positive coordinates:", ""]
            for positive in sweep["positive_coordinates"]:
                lines.append(
                    f"  - tile ({positive['tile'][0]},{positive['tile'][1]}) "
                    f"{positive['bit']} delta {positive['conflict_net_delta']}"
                )
        lines.append("")

    lines += [
        "## Tracked fixture ASCs",
        "",
        "These are the checked-in artifacts `make verify-repro` recreates byte for byte.",
        "",
    ]
    for asc, digest in manifest["tracked_ascs"].items():
        lines.append(f"- `work/{asc}`: `{digest}`")
    lines.append("")

    (DOCS / "evidence_manifest.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {DOCS / 'evidence_manifest.json'} and {DOCS / 'evidence_manifest.md'}")
    failures = [entry for entry in manifest["fixtures"] if entry.get("status") == "fail"]
    return 1 if failures else 0


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if "--self-test" in arguments:
        raise SystemExit(self_test())
    raise SystemExit(check() if "--check" in arguments else main())

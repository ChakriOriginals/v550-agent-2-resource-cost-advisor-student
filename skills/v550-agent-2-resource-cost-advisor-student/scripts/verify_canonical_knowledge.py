#!/usr/bin/env python3
"""Verify frozen source hashes, runtime-reference hashes, and fixed engine values."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

EXPECTED_SOURCES = {
    "Scenario 2 - Making Time.docx": "90aaf0f49b85d2ab5f4fd8b4fe5f20e0b024f74dae2087974c616c83314e7adb",
    "Scenario 1 After the Merger V2.docx": "655af3b8c7e34ca675dc5b78ef7b03d8854565b89eab01ba2553fb81b7c96d3e",
    "Resource and Cost Advisor Workflow.docx": "0b484d5eed4b19537aecca9bac7b9248f88860ce1c4da5d1e0f73685eab62527",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("v550_agent2_cost_engine", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load deterministic engine.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    skill = args.repo_root.resolve() / "skills" / "v550-agent-2-resource-cost-advisor-student"
    references = skill / "references"
    errors: list[str] = []
    try:
        manifest = json.loads((references / "canonical-source-manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, indent=2))
        return 1
    actual_sources = {item.get("filename"): item.get("sha256") for item in manifest.get("source_documents", []) if isinstance(item, dict)}
    if actual_sources != EXPECTED_SOURCES:
        errors.append("Canonical source-document hashes do not match the supplied files.")
    runtime = manifest.get("runtime_references")
    if not isinstance(runtime, dict):
        errors.append("Runtime reference inventory is missing.")
    else:
        for name, expected in runtime.items():
            path = references / name
            if not path.is_file():
                errors.append(f"Missing runtime reference: {name}")
            elif sha256_file(path) != expected:
                errors.append(f"Runtime reference hash mismatch: {name}")
    try:
        engine = load_engine(skill / "scripts" / "cost_engine.py")
        if engine.RATES != {"Marcus Feld": Decimal("43"), "Priya Raghavan": Decimal("34"), "Tomas Beltrán": Decimal("36")}:
            errors.append("Engine labor rates differ from Scenario 2 version 1.0.")
        if engine.WEEKLY_CAPACITY != {"Marcus Feld": Decimal("16"), "Priya Raghavan": Decimal("8"), "Tomas Beltrán": Decimal("6")}:
            errors.append("Engine weekly capacities differ from Scenario 2.")
        if engine.CASH_CEILING != Decimal("35000") or engine.PRE_VOTE_CEILING != Decimal("525") or engine.POST_VOTE_CEILING != Decimal("65.5"):
            errors.append("Engine budget or staff-time ceilings differ from Scenario 2.")
        expected_cash = {
            "FACILITATOR_DAY": Decimal("1200"), "OUTSIDE_PARTICIPANT_STIPEND": Decimal("75"),
            "ROOM_SCHEDULING_SOFTWARE_MONTH": Decimal("200"), "PRINT_BW_PAGE": Decimal("0.10"),
            "PRINT_COLOR_PAGE": Decimal("0.50"), "LARGE_FORMAT_FLOOR_PLAN": Decimal("15"),
        }
        if engine.CASH_RULES != expected_cash:
            errors.append("Engine cash unit costs differ from Scenario 2.")
    except Exception as exc:
        errors.append(f"Cannot verify engine constants: {exc}")
    result = {
        "valid": not errors,
        "source_documents_verified": len(EXPECTED_SOURCES),
        "runtime_references_verified": len(runtime) if isinstance(runtime, dict) and not errors else 0,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())


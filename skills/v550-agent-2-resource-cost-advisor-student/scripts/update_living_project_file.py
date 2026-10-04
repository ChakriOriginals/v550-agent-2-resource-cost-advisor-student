#!/usr/bin/env python3
"""Create a versioned local Markdown Living Project File from packet and engine output."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows recorded._"
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join("---" for _ in columns) + "|"
    body = []
    for row in rows:
        values = [str(row.get(column, "")).replace("|", "\\|").replace("\n", " ") for column in columns]
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, divider, *body])


def render(packet: dict[str, Any], result: dict[str, Any], version: int, timestamp: str) -> str:
    project = packet.get("project", {}) if isinstance(packet.get("project"), dict) else {}
    calculations = result.get("calculations", {})
    readiness = result.get("readiness", {})
    wbs = packet.get("approved_wbs", [])
    phases = packet.get("phases", [])
    estimates = packet.get("estimates", [])
    embedded = json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True)
    sections = [
        "# V550 Agent 2 Living Project File",
        f"- Schema version: 2.0.0\n- File version: {version}\n- Saved at UTC: {timestamp}\n"
        f"- Project: {project.get('title', 'After the Merger: One Building, Nine Desks')}\n"
        f"- Source WBS filename: {project.get('source_wbs_filename', '')}\n"
        f"- Source WBS SHA-256: {project.get('source_wbs_sha256', '')}\n"
        f"- Source WBS version: {project.get('source_wbs_version', '')}\n"
        f"- Fixed rate table: 1.0 approved 2027-01-05",
        "## Normalized WBS\n\n" + table(wbs, ["wbs_id", "title", "parent_id", "deliverable_id", "scope_status", "timing_label", "phase_id", "owner"]),
        "## Phase Map\n\n" + table(phases, ["phase_id", "name", "start_date", "end_date"]),
        "## Paper and Realistic Capacity\n\n" + table(calculations.get("capacity", []), ["phase_id", "resource", "paper_hours", "realistic_hours", "assigned_hours_including_contingency", "paper_overallocated", "realistic_overallocated"]),
        "## Ownership and Labor Estimates\n\n" + table(estimates, ["wbs_id", "most_likely_hours", "method", "evidence"]),
        "## Cash Quantities and Costs\n\n" + table(calculations.get("cash_lines", []), ["line_id", "category", "entered_quantity", "billed_quantity", "unit_cost", "unrounded_cost", "reason"]),
        "## Three Point Estimates and Contingency\n\n" + table(calculations.get("uncertainty_packages", []), ["wbs_id", "optimistic_hours", "most_likely_hours", "expected_hours_rounded_up", "pessimistic_hours"])
        + f"\n\nSelected contingency: {json.dumps(packet.get('contingency', {}), ensure_ascii=False)}",
        "## Deterministic Output\n\n```json\n" + json.dumps(calculations, indent=2, ensure_ascii=False, sort_keys=True) + "\n```",
        "## Conflicts and Resolutions\n\n```json\n" + json.dumps(packet.get("conflicts", []), indent=2, ensure_ascii=False) + "\n```",
        "## WBS Corrections\n\n```json\n" + json.dumps(packet.get("wbs_corrections", []), indent=2, ensure_ascii=False) + "\n```",
        "## Scope Changes\n\n```json\n" + json.dumps(packet.get("scope_changes", []), indent=2, ensure_ascii=False) + "\n```",
        "## Overrides and Accepted Flags\n\n```json\n" + json.dumps(packet.get("accepted_flags", []), indent=2, ensure_ascii=False) + "\n```",
        "## Assumptions Trade Offs and Limitations\n\n```json\n" + json.dumps({key: packet.get(key, []) for key in ("assumptions", "tradeoffs", "limitations")}, indent=2, ensure_ascii=False) + "\n```",
        "## Final Explanation\n\n" + str(packet.get("final_explanation", "")),
        "## Readiness History\n\n```json\n" + json.dumps(readiness, indent=2, ensure_ascii=False, sort_keys=True) + "\n```",
        "## Revision History\n\n" + table(packet.get("revisions", []), ["timestamp", "affected_item", "previous_value", "new_value", "student_reason"]),
        "<!-- V550_AGENT2_PACKET_JSON\n" + embedded + "\nEND_V550_AGENT2_PACKET_JSON -->",
    ]
    return "\n\n".join(sections) + "\n"


def next_version(output_root: Path) -> int:
    versions = []
    for path in output_root.glob("V550_AGENT2_LIVING_PROJECT_FILE_v*.md"):
        match = re.search(r"_v(\d+)\.md$", path.name)
        if match:
            versions.append(int(match.group(1)))
    return max(versions, default=0) + 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("engine_result", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path.cwd() / "V550 Agent 2 Work")
    args = parser.parse_args(argv)
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        result = json.loads(args.engine_result.read_text(encoding="utf-8"))
        output_root = args.output_root.resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        version = next_version(output_root)
        timestamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        destination = output_root / f"V550_AGENT2_LIVING_PROJECT_FILE_v{version:03d}.md"
        destination.write_text(render(packet, result, version, timestamp), encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"saved": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"saved": True, "path": str(destination), "version": version}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


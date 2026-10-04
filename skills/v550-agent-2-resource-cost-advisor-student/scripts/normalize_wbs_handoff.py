#!/usr/bin/env python3
"""Safely extract and normalize an untrusted Agent 1 WBS handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_MEMBER_BYTES = 10 * 1024 * 1024
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
VOTE_DATE = date(2027, 5, 14)
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
}
OWNER_NAMES = {
    "marcus": "Marcus Feld",
    "marcus feld": "Marcus Feld",
    "priya": "Priya Raghavan",
    "priya raghavan": "Priya Raghavan",
    "tomas": "Tomas Beltrán",
    "tomas beltran": "Tomas Beltrán",
    "tomas beltrán": "Tomas Beltrán",
}
ALIASES = {
    "wbs_id": {"wbs id", "wbs #", "wbs number", "wbs_id", "id", "work package id", "work_package_id"},
    "title": {"title", "work package", "work package title", "name"},
    "parent_id": {"parent", "parent id", "parent_id"},
    "deliverable_id": {"deliverable", "deliverable id", "deliverable_id", "deliverable link"},
    "scope_status": {"scope status", "scope_status", "approved scope status", "status"},
    "timing_label": {"timing", "timing label", "timing_label", "window"},
    "owner": {"owner", "accountable owner", "assigned party", "assigned to", "assignee"},
    "source_hours": {"hours", "estimated hours", "estimate", "source hours", "source_hours"},
    "deadline": {"deadline", "due", "due date", "target date"},
    "row_type": {"row type", "row_type", "type"},
    "phase_id": {"phase", "phase id", "phase_id"},
    "approval_status": {"approval status", "approval_status"},
    "change_reason": {"change reason", "change_reason"},
}


class HandoffError(ValueError):
    """The upload cannot be normalized without inventing semantic content."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_member(name: str) -> None:
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts or "\\" in name:
        raise HandoffError(f"Unsafe ZIP path rejected: {name}")


def normalize_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().casefold())


def header_map(headers: list[str]) -> dict[int, str]:
    mapped: dict[int, str] = {}
    for index, raw in enumerate(headers):
        key = normalize_key(raw)
        for canonical, aliases in ALIASES.items():
            if key == canonical or key in aliases:
                mapped[index] = canonical
                break
    return mapped


def canonical_row(source: dict[str, Any]) -> dict[str, Any]:
    normalized_source = {normalize_key(key): value for key, value in source.items()}
    row: dict[str, Any] = {}
    for canonical, aliases in ALIASES.items():
        for candidate in (canonical, *sorted(aliases)):
            key = normalize_key(candidate)
            if key in normalized_source:
                row[canonical] = normalized_source[key]
                break
    return row


def text_value(value: Any) -> str:
    return value if isinstance(value, str) else "" if value is None else str(value)


def decimal_value(value: Any) -> Decimal | None:
    text = text_value(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise HandoffError(f"Hours value {text!r} is not numeric.") from exc


def approved_agent1_statement(source_text: str) -> str | None:
    patterns = (
        r"WBS\s+as\s+approved\s+by\s+Agent\s*1",
        r"approved\s+Agent\s*1\s+WBS",
        r"final\s+approved\s+WBS",
    )
    for pattern in patterns:
        match = re.search(pattern, source_text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def deadline_date(value: Any) -> date | None:
    text = re.sub(r"\s+", " ", text_value(value).strip())
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    match = re.fullmatch(r"([A-Za-z]+)\.?\s+(\d{1,2})(?:,?\s+2027)?", text)
    if not match:
        return None
    month = MONTHS.get(match.group(1).casefold())
    if month is None:
        return None
    try:
        return date(2027, month, int(match.group(2)))
    except ValueError:
        return None


def timing_from_deadline(value: Any) -> str | None:
    resolved = deadline_date(value)
    if resolved is None:
        return None
    return "PRE_VOTE" if resolved <= VOTE_DATE else "POST_VOTE"


def numeric_wbs_parts(wbs_id: str) -> list[int] | None:
    stripped = wbs_id.strip()
    if not re.fullmatch(r"\d+(?:\.\d+)+", stripped):
        return None
    return [int(part) for part in stripped.split(".")]


def derived_links(wbs_id: str, deliverable_ids: dict[str, str], all_ids: dict[str, str]) -> tuple[str | None, str | None]:
    parts = numeric_wbs_parts(wbs_id)
    if not parts or len(parts) < 2 or parts[-1] == 0:
        return None, None
    deliverable_id = deliverable_ids.get(f"{parts[0]}.0")
    if deliverable_id is None:
        return None, None
    if len(parts) == 2:
        return deliverable_id, deliverable_id
    parent_key = ".".join(str(part) for part in parts[:-1])
    return all_ids.get(parent_key), deliverable_id


def is_deliverable_summary(row: dict[str, Any]) -> bool:
    if normalize_key(row.get("row_type", "")) in {"deliverable", "summary", "deliverable summary"}:
        return True
    parts = numeric_wbs_parts(text_value(row.get("wbs_id")))
    return bool(parts and len(parts) == 2 and parts[-1] == 0)


def normalize_rows(rows: list[dict[str, Any]], source_text: str = "") -> dict[str, Any]:
    canonical: list[dict[str, Any]] = []
    declared_total: Decimal | None = None
    seen_keys: set[str] = set()
    for index, source in enumerate(rows):
        if not isinstance(source, dict):
            raise HandoffError(f"WBS row {index + 1} is not an object.")
        row = canonical_row(source)
        wbs_id = text_value(row.get("wbs_id"))
        title = text_value(row.get("title"))
        if normalize_key(wbs_id) == "total" or normalize_key(title) == "total":
            declared_total = decimal_value(row.get("source_hours"))
            continue
        if not wbs_id.strip() and not title.strip():
            continue
        if not wbs_id.strip():
            raise HandoffError(f"WBS row {index + 1} is missing required field wbs_id.")
        if not title.strip():
            raise HandoffError(f"WBS row {index + 1} ({wbs_id!r}) is missing required field title.")
        duplicate_key = wbs_id.strip()
        if duplicate_key in seen_keys:
            raise HandoffError(f"Duplicate WBS ID rejected: {wbs_id!r}.")
        seen_keys.add(duplicate_key)
        row["wbs_id"] = wbs_id
        row["title"] = title
        canonical.append(row)
    if not canonical:
        raise HandoffError("No structured WBS rows were found.")

    all_ids = {row["wbs_id"].strip(): row["wbs_id"] for row in canonical}
    deliverable_ids = {row["wbs_id"].strip(): row["wbs_id"] for row in canonical if is_deliverable_summary(row)}
    approval_statement = approved_agent1_statement(source_text)
    deliverables: list[dict[str, Any]] = []
    approved_wbs: list[dict[str, Any]] = []
    derivation_count = 0

    for index, source in enumerate(canonical):
        wbs_id = source["wbs_id"]
        source_hours = text_value(source.get("source_hours")).strip() or None
        deadline = text_value(source.get("deadline")).strip() or None
        scope_status = text_value(source.get("scope_status")).strip() or None
        scope_source = "EXPLICIT_ROW"
        if scope_status is None and approval_statement:
            scope_status = "APPROVED"
            scope_source = "DOCUMENT_APPROVAL_STATEMENT"
            derivation_count += 1
        if scope_status is None:
            raise HandoffError(
                f"WBS row {index + 1} ({wbs_id!r}) has no scope_status and the document does not state that this is an approved Agent 1 WBS."
            )
        if scope_status not in {"APPROVED", "WBS_CORRECTION", "SCOPE_CHANGE"}:
            raise HandoffError(f"WBS row {index + 1} ({wbs_id!r}) has invalid scope_status {scope_status!r}.")

        if is_deliverable_summary(source):
            deliverables.append({
                "deliverable_id": wbs_id,
                "title": source["title"],
                "source_hours": source_hours,
                "deadline": deadline,
                "scope_status": scope_status,
                "field_sources": {
                    "deliverable_id": "EXPLICIT_WBS_NUMBER",
                    "scope_status": scope_source,
                    "source_hours": "EXPLICIT_ROW" if source_hours is not None else None,
                    "deadline": "EXPLICIT_ROW" if deadline is not None else None,
                },
                "supporting_wbs_ids": [],
            })
            continue

        parent_id = text_value(source.get("parent_id")).strip() or None
        deliverable_id = text_value(source.get("deliverable_id")).strip() or None
        derived_parent, derived_deliverable = derived_links(wbs_id, deliverable_ids, all_ids)
        parent_source = "EXPLICIT_ROW"
        deliverable_source = "EXPLICIT_ROW"
        if parent_id is None and derived_parent is not None:
            parent_id = derived_parent
            parent_source = "WBS_NUMBERING"
            derivation_count += 1
        if deliverable_id is None and derived_deliverable is not None:
            deliverable_id = derived_deliverable
            deliverable_source = "WBS_NUMBERING"
            derivation_count += 1
        if deliverable_id is None:
            raise HandoffError(
                f"WBS row {index + 1} ({wbs_id!r}) has no deliverable link and one cannot be derived from an included numeric deliverable row."
            )
        if parent_id is None:
            raise HandoffError(
                f"WBS row {index + 1} ({wbs_id!r}) has no parent link and one cannot be derived from the WBS numbering."
            )

        timing_label = text_value(source.get("timing_label")).strip() or None
        timing_source = "EXPLICIT_ROW"
        if timing_label is None and deadline is not None:
            timing_label = timing_from_deadline(deadline)
            if timing_label is not None:
                timing_source = "FIXED_MAY_14_BOUNDARY_FROM_DEADLINE"
                derivation_count += 1
        if timing_label not in {"PRE_VOTE", "POST_VOTE"}:
            raise HandoffError(
                f"WBS row {index + 1} ({wbs_id!r}) needs PRE_VOTE or POST_VOTE; deadline {deadline!r} is not specific enough to classify deterministically."
            )

        owner = text_value(source.get("owner")).strip() or None
        owner_source = "EXPLICIT_ROW"
        if owner is not None and normalize_key(owner) in OWNER_NAMES:
            expanded = OWNER_NAMES[normalize_key(owner)]
            if expanded != owner:
                owner = expanded
                owner_source = "FIXED_TEAM_ROSTER_NAME_EXPANSION"
                derivation_count += 1

        normalized = {
            "wbs_id": wbs_id,
            "title": source["title"],
            "parent_id": parent_id,
            "deliverable_id": deliverable_id,
            "scope_status": scope_status,
            "timing_label": timing_label,
            "owner": owner,
            "source_hours": source_hours,
            "deadline": deadline,
            "row_type": "WORK_PACKAGE",
            "field_sources": {
                "wbs_id": "EXPLICIT_ROW",
                "title": "EXPLICIT_ROW",
                "parent_id": parent_source,
                "deliverable_id": deliverable_source,
                "scope_status": scope_source,
                "timing_label": timing_source,
                "owner": owner_source if owner is not None else None,
                "source_hours": "EXPLICIT_ROW" if source_hours is not None else None,
                "deadline": "EXPLICIT_ROW" if deadline is not None else None,
            },
        }
        for optional in ("phase_id", "approval_status", "change_reason"):
            if source.get(optional) is not None:
                normalized[optional] = source[optional]
        approved_wbs.append(normalized)

    deliverable_by_id = {item["deliverable_id"]: item for item in deliverables}
    for work_package in approved_wbs:
        deliverable = deliverable_by_id.get(work_package["deliverable_id"])
        if deliverable is not None:
            deliverable["supporting_wbs_ids"].append(work_package["wbs_id"])

    for deliverable in deliverables:
        child_rows = [row for row in approved_wbs if row["deliverable_id"] == deliverable["deliverable_id"]]
        child_hours = [decimal_value(row.get("source_hours")) for row in child_rows]
        complete_hours = all(value is not None for value in child_hours)
        child_total = sum((value for value in child_hours if value is not None), Decimal("0")) if complete_hours else None
        summary_hours = decimal_value(deliverable.get("source_hours"))
        deliverable["supporting_source_hours_total"] = str(child_total) if child_total is not None else None
        deliverable["source_hours_reconciles"] = summary_hours == child_total if summary_hours is not None and child_total is not None else None
        child_timings = {row["timing_label"] for row in child_rows}
        deliverable["timing_label"] = next(iter(child_timings)) if len(child_timings) == 1 else "MIXED" if child_timings else None

    leaf_hours = [decimal_value(row.get("source_hours")) for row in approved_wbs]
    leaf_hours_complete = all(value is not None for value in leaf_hours)
    leaf_total = sum((value for value in leaf_hours if value is not None), Decimal("0")) if leaf_hours_complete else None
    source_summary = {
        "declared_total_hours": str(declared_total) if declared_total is not None else None,
        "leaf_work_package_total_hours": str(leaf_total) if leaf_total is not None else None,
        "hours_reconcile": declared_total == leaf_total if declared_total is not None and leaf_total is not None else None,
    }
    return {
        "approved_wbs": approved_wbs,
        "deliverables": deliverables,
        "source_hours_summary": source_summary,
        "approval_statement": approval_statement,
        "derived_field_count": derivation_count,
    }


def rows_from_json(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        raise HandoffError("JSON root must be an object or list.")
    for key in ("approved_wbs", "normalized_wbs", "wbs"):
        if isinstance(data.get(key), list):
            return data[key]
    for key in ("structured_work", "packet", "project_record"):
        nested = data.get(key)
        if isinstance(nested, dict):
            try:
                return rows_from_json(nested)
            except HandoffError:
                pass
    raise HandoffError("JSON contains no approved_wbs, normalized_wbs, or wbs list.")


def rows_from_markdown(text: str) -> list[dict[str, Any]]:
    embedded = re.search(r"<!--\s*V550_AGENT2_PACKET_JSON\s*\n(.*?)\nEND_V550_AGENT2_PACKET_JSON\s*-->", text, re.DOTALL)
    if embedded:
        return rows_from_json(json.loads(embedded.group(1)))
    lines = text.splitlines()
    for index in range(len(lines) - 2):
        if "|" not in lines[index] or not re.fullmatch(r"\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*", lines[index + 1]):
            continue
        headers = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        mapped = header_map(headers)
        if "wbs_id" not in mapped.values():
            continue
        extracted: list[dict[str, Any]] = []
        for line in lines[index + 2:]:
            if "|" not in line or not line.strip():
                break
            values = [cell.strip() for cell in line.strip().strip("|").split("|")]
            extracted.append({field: values[position] if position < len(values) else "" for position, field in mapped.items()})
        return extracted
    raise HandoffError("No structured Markdown WBS table was found.")


def docx_content(data: bytes) -> tuple[list[list[list[str]]], str]:
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = archive.namelist()
        for name in names:
            safe_member(name)
            lower = name.casefold()
            if "vbaproject" in lower or lower.endswith((".bin", ".exe", ".js")):
                raise HandoffError("Macro or executable content is not allowed in a WBS DOCX.")
        if "word/document.xml" not in names:
            raise HandoffError("DOCX has no word/document.xml.")
        if archive.getinfo("word/document.xml").file_size > MAX_MEMBER_BYTES:
            raise HandoffError("DOCX document XML is too large.")
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    document_text = " ".join((node.text or "") for node in root.iter(W_NS + "t"))
    tables: list[list[list[str]]] = []
    for table in root.iter(W_NS + "tbl"):
        table_rows: list[list[str]] = []
        for tr in table.findall("./" + W_NS + "tr"):
            cells: list[str] = []
            for tc in tr.findall("./" + W_NS + "tc"):
                fragments = [node.text or "" for node in tc.iter(W_NS + "t")]
                cells.append("".join(fragments).strip())
            table_rows.append(cells)
        tables.append(table_rows)
    return tables, document_text


def rows_from_docx(data: bytes) -> tuple[list[dict[str, Any]], str]:
    tables, document_text = docx_content(data)
    for table in tables:
        if len(table) < 2:
            continue
        mapped = header_map(table[0])
        if "wbs_id" not in mapped.values() or "title" not in mapped.values():
            continue
        return [
            {field: row[position] if position < len(row) else "" for position, field in mapped.items()}
            for row in table[1:] if any(cell.strip() for cell in row)
        ], document_text
    raise HandoffError("No structured WBS table with a WBS number and work-package title was found in the DOCX.")


def extract_zip(path: Path) -> tuple[list[dict[str, Any]], str]:
    with zipfile.ZipFile(path) as archive:
        candidates: list[tuple[str, bytes]] = []
        for info in archive.infolist():
            safe_member(info.filename)
            if info.is_dir():
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                raise HandoffError(f"ZIP member is too large: {info.filename}")
            if Path(info.filename).suffix.casefold() in {".json", ".md", ".docx"}:
                candidates.append((info.filename, archive.read(info)))
        preferred = sorted(candidates, key=lambda item: ("REVIEW_RECORD" not in item[0].upper(), item[0]))
        errors: list[str] = []
        for name, data in preferred:
            try:
                suffix = Path(name).suffix.casefold()
                if suffix == ".json":
                    decoded = data.decode("utf-8")
                    return rows_from_json(json.loads(decoded)), decoded
                if suffix == ".md":
                    decoded = data.decode("utf-8")
                    return rows_from_markdown(decoded), decoded
                return rows_from_docx(data)
            except (HandoffError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"{name}: {exc}")
        raise HandoffError("ZIP contains no readable structured WBS. " + "; ".join(errors[:3]))


def load_handoff(path: Path) -> tuple[list[dict[str, Any]], str]:
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise HandoffError("WBS input exceeds the 25 MB local limit.")
    suffix = path.suffix.casefold()
    if suffix == ".json":
        text = path.read_text(encoding="utf-8")
        return rows_from_json(json.loads(text)), text
    if suffix in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8")
        return rows_from_markdown(text), text
    if suffix == ".docx":
        return rows_from_docx(path.read_bytes())
    if suffix == ".zip":
        return extract_zip(path)
    raise HandoffError("Supported WBS inputs are JSON, Markdown, text, DOCX, or ZIP.")


def living_project_metadata(source: Path, source_text: str, expected_hash: str | None) -> dict[str, Any] | None:
    if source.suffix.casefold() not in {".md", ".txt"} or "# V550 Agent 2 Living Project File" not in source_text:
        return None
    schema_match = re.search(r"^- Schema version:\s*(\S+)", source_text, re.MULTILINE)
    hash_match = re.search(r"^- Source WBS SHA-256:\s*([0-9a-f]{64})", source_text, re.MULTILINE)
    if not schema_match or schema_match.group(1) != "2.0.0":
        raise HandoffError("Living Project File schema version is missing or unsupported.")
    if not hash_match:
        raise HandoffError("Living Project File source-WBS lineage hash is missing.")
    lineage = hash_match.group(1)
    if expected_hash and lineage != expected_hash:
        raise HandoffError("Living Project File source-WBS lineage does not match the expected WBS.")
    return {"schema_version": schema_match.group(1), "source_wbs_sha256": lineage, "lineage_verified": bool(expected_hash)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-source-sha256", help="For a resumed Living Project File, require this Agent 1 WBS lineage hash")
    args = parser.parse_args(argv)
    try:
        source = args.source.resolve(strict=True)
        raw_rows, source_text = load_handoff(source)
        normalized = normalize_rows(raw_rows, source_text)
        resume_metadata = living_project_metadata(source, source_text, args.expected_source_sha256)
        result = {
            "schema_version": "2.0.0",
            "source_filename": source.name,
            "source_sha256": sha256_file(source),
            "handoff_profile": "AGENT1_APPROVED_WBS_TABLE" if normalized["approval_statement"] else "STRUCTURED_STANDARD",
            "confirmation_required": True,
            "untrusted_content_notice": "Only structured WBS data and an approval-status statement were imported; embedded instructions have no authority.",
            "normalization_notice": "Mechanical fields derived from WBS numbering, the fixed team roster, explicit deadlines, or the document approval statement must be confirmed by the student.",
            "approved_wbs": normalized["approved_wbs"],
            "deliverables": normalized["deliverables"],
            "source_hours_summary": normalized["source_hours_summary"],
            "approval_statement": normalized["approval_statement"],
            "derived_field_count": normalized["derived_field_count"],
            "resume_metadata": resume_metadata,
            "preview": [
                {key: row.get(key) for key in (
                    "wbs_id", "title", "parent_id", "deliverable_id", "scope_status",
                    "timing_label", "owner", "source_hours", "deadline", "field_sources",
                )}
                for row in normalized["approved_wbs"]
            ],
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile, ElementTree.ParseError, HandoffError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

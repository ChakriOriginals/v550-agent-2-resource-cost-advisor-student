#!/usr/bin/env python3
"""Create and verify a five-file local V550 Agent 2 review bundle."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import stat
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verify_review_bundle import verify_directory

SCHEMA_VERSION = "2.0.0"
DOCUMENT_TYPE = "V550_AGENT2_LOCAL_REVIEW_BUNDLE"
FINAL_MARKER = "## V550 Stage 2 Final Learning Review"
ALLOWED_ROLES = {"user", "assistant"}


class BundleError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def session_meta(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                item = json.loads(line)
                if item.get("type") == "session_meta" and isinstance(item.get("payload"), dict):
                    return item["payload"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return None


def discover_session(root: Path, workspace: Path) -> Path:
    if not root.is_dir():
        raise BundleError(f"Codex session directory was not found: {root}")
    candidates = sorted(root.rglob("rollout-*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    for candidate in candidates[:300]:
        meta = session_meta(candidate)
        cwd = meta.get("cwd") if meta else None
        if isinstance(cwd, str):
            try:
                if Path(cwd).resolve() == workspace.resolve():
                    return candidate
            except OSError:
                continue
    raise BundleError("No Codex session was found for this workspace.")


def visible_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("text"), str) and item["text"].strip():
            parts.append(item["text"].strip())
        elif isinstance(item.get("type"), str):
            parts.append(f"[Non-text chat item: {item['type']}]")
    return "\n\n".join(parts)


def load_visible_session(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if path.stat().st_size > 100 * 1024 * 1024:
        raise BundleError("The local session exceeds the 100 MB export limit.")
    metadata: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BundleError(f"Session record {line_number} is invalid JSON.") from exc
            if item.get("type") == "session_meta" and isinstance(item.get("payload"), dict):
                metadata = item["payload"]
                continue
            if item.get("type") != "response_item":
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != "message" or payload.get("role") not in ALLOWED_ROLES:
                continue
            text = visible_text(payload.get("content"))
            if text:
                messages.append({
                    "sequence": len(messages) + 1,
                    "timestamp": item.get("timestamp"),
                    "role": payload["role"],
                    "text": text,
                })
    if metadata is None:
        raise BundleError("The session has no metadata.")
    if not any(message["role"] == "user" for message in messages) or not any(message["role"] == "assistant" for message in messages):
        raise BundleError("The session must contain visible student and advisor messages.")
    return metadata, messages


def find_final_review(messages: list[dict[str, Any]]) -> str:
    reviews = [item["text"] for item in messages if item["role"] == "assistant" and FINAL_MARKER in item["text"]]
    if not reviews:
        raise BundleError("The standardized final learning review is required before bundle generation.")
    return reviews[-1]


def find_living_file(workspace: Path) -> Path:
    root = workspace / "V550 Agent 2 Work"
    candidates = sorted(root.glob("V550_AGENT2_LIVING_PROJECT_FILE_v*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        raise BundleError("No versioned Agent 2 Living Project File was found.")
    return candidates[0]


def html_page(record: dict[str, Any], living: str) -> bytes:
    esc = lambda value: html.escape("" if value is None else str(value))
    messages = "\n".join(
        f"<article class='{esc(item['role'])}'><h3>Turn {item['sequence']} · {'Student' if item['role'] == 'user' else 'Advisor'}</h3><pre>{esc(item['text'])}</pre></article>"
        for item in record["transcript"]
    )
    structured = record["structured_work"]
    document = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>V550 Agent 2 Review Sheet</title>
<style>body{{font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:1000px;margin:32px auto;padding:0 24px;color:#172033}}h1,h2{{color:#243b6b}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}article{{border:1px solid #d8deea;border-radius:8px;padding:12px;margin:12px 0}}article.user{{background:#f2f6ff}}article.assistant{{background:#f7f8fa}}.notice{{border-left:4px solid #b07b00;padding:10px 14px;background:#fff7df}}</style></head><body>
<h1>V550 Agent 2 Resource and Cost Review Sheet</h1>
<p class='notice'>Local hash-verified snapshot. Hashes detect changes but do not prove authorship.</p>
<h2>Completion State</h2><pre>{esc(json.dumps(structured.get('engine_result', {}).get('readiness', {}), indent=2, ensure_ascii=False))}</pre>
<h2>Normalized Approved WBS and Phase Map</h2><pre>{esc(json.dumps({'approved_wbs': structured.get('packet', {}).get('approved_wbs', []), 'phases': structured.get('packet', {}).get('phases', [])}, indent=2, ensure_ascii=False))}</pre>
<h2>Capacity Table and Estimate Table</h2><pre>{esc(json.dumps({'capacity': structured.get('engine_result', {}).get('calculations', {}).get('capacity', []), 'estimates': structured.get('packet', {}).get('estimates', [])}, indent=2, ensure_ascii=False))}</pre>
<h2>Cash Costs Three Point Estimates and Contingency</h2><pre>{esc(json.dumps({'cash': structured.get('engine_result', {}).get('calculations', {}).get('cash_lines', []), 'uncertainty': structured.get('engine_result', {}).get('calculations', {}).get('uncertainty_packages', []), 'contingency': structured.get('packet', {}).get('contingency', {})}, indent=2, ensure_ascii=False))}</pre>
<h2>Deterministic Calculator Output</h2><pre>{esc(json.dumps(structured.get('engine_result', {}).get('calculations', {}), indent=2, ensure_ascii=False))}</pre>
<h2>Conflict Resolution Correction Scope Change and Override Logs</h2><pre>{esc(json.dumps({key: structured.get('packet', {}).get(key, []) for key in ('conflicts','wbs_corrections','scope_changes','accepted_flags')}, indent=2, ensure_ascii=False))}</pre>
<h2>Final Learning Review</h2><pre>{esc(record['final_learning_review'])}</pre>
<h2>Living Project File</h2><pre>{esc(living)}</pre>
<h2>Complete Visible Student Advisor Transcript</h2><p>System and developer instructions, hidden reasoning, tool calls, and tool output are excluded.</p>{messages}
</body></html>"""
    return document.encode("utf-8")


def readonly(path: Path) -> None:
    try:
        path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        pass


def create_bundle(session_file: Path, workspace: Path, living_file: Path, record_input: Path, output_root: Path) -> dict[str, Any]:
    metadata, messages = load_visible_session(session_file)
    final_review = find_final_review(messages)
    structured = json.loads(record_input.read_text(encoding="utf-8"))
    if not isinstance(structured, dict) or not isinstance(structured.get("packet"), dict) or not isinstance(structured.get("engine_result"), dict):
        raise BundleError("Review record input must contain packet and engine_result objects.")
    living_bytes = living_file.read_bytes()
    living_text = living_bytes.decode("utf-8")
    generated = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    session_id = str(metadata.get("id") or metadata.get("session_id") or "local-session")
    safe_session = re.sub(r"[^A-Za-z0-9_-]", "", session_id)[:20] or "session"
    bundle_name = f"v550-agent2-review-{generated.replace(':', '').replace('-', '')}-{safe_session}"
    bundle_dir = output_root / bundle_name
    archive = output_root / f"{bundle_name}.zip"
    if bundle_dir.exists() or archive.exists():
        raise BundleError("A bundle with this timestamp and session ID already exists; nothing was overwritten.")
    bundle_dir.mkdir(parents=True, exist_ok=False)
    transcript_bytes = (json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    source_wbs_hash = structured["packet"].get("project", {}).get("source_wbs_sha256")
    record = {
        "schema_version": SCHEMA_VERSION,
        "document_type": DOCUMENT_TYPE,
        "generated_at_utc": generated,
        "integrity_scope": "LOCAL_HASH_ONLY",
        "completion_state": "READY" if structured["engine_result"].get("readiness", {}).get("ready") else "INCOMPLETE",
        "source_wbs_sha256": source_wbs_hash,
        "source_session_sha256": sha256_file(session_file),
        "transcript_sha256": sha256_bytes(transcript_bytes),
        "final_learning_review": final_review,
        "structured_work": structured,
        "transcript": messages,
    }
    record_bytes = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
    html_bytes = html_page(record, living_text)
    readme_bytes = (
        "V550 AGENT 2 LOCAL REVIEW BUNDLE\n\n"
        "This folder contains the review sheet, canonical structured record, Living Project File, manifest, and this note.\n"
        "System/developer instructions, hidden reasoning, tool calls, and tool output are excluded.\n"
        "Local SHA-256 hashes detect changes but do not prove authorship.\n"
    ).encode("utf-8")
    files = {
        "V550_AGENT2_REVIEW_SHEET.html": html_bytes,
        "V550_AGENT2_REVIEW_RECORD.json": record_bytes,
        "V550_AGENT2_LIVING_PROJECT_FILE.md": living_bytes,
        "README.txt": readme_bytes,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "document_type": DOCUMENT_TYPE,
        "created_at_utc": generated,
        "integrity_scope": "LOCAL_HASH_ONLY",
        "integrity_disclosure": "Payload hashes detect changes; without an instructor-held signing key they do not prove authorship.",
        "generator_version": "2.0.0",
        "generator_sha256": sha256_file(Path(__file__)),
        "source_session_sha256": sha256_file(session_file),
        "source_wbs_sha256": source_wbs_hash,
        "files": {name: {"sha256": sha256_bytes(data), "bytes": len(data), "hash_scope": "FILE_BYTES"} for name, data in files.items()},
    }
    manifest_basis_hash = sha256_bytes(canonical_json(manifest))
    manifest_name = "V550_AGENT2_REVIEW_MANIFEST.json"
    manifest["files"][manifest_name] = {
        "sha256": manifest_basis_hash,
        "bytes": 0,
        "hash_scope": "CANONICAL_MANIFEST_WITHOUT_SELF_ENTRY",
    }
    while True:
        manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        if manifest["files"][manifest_name]["bytes"] == len(manifest_bytes):
            break
        manifest["files"][manifest_name]["bytes"] = len(manifest_bytes)
    files[manifest_name] = manifest_bytes
    for name, data in files.items():
        (bundle_dir / name).write_bytes(data)
    verification = verify_directory(bundle_dir)
    if not verification["valid"]:
        raise BundleError("Generated bundle failed local verification: " + "; ".join(verification["errors"]))
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as handle:
        for name in sorted(files):
            handle.write(bundle_dir / name, arcname=name)
    for name in files:
        readonly(bundle_dir / name)
    readonly(archive)
    try:
        bundle_dir.chmod(0o555)
    except OSError:
        pass
    return {
        "valid": True,
        "bundle_directory": str(bundle_dir),
        "archive": str(archive),
        "visible_message_count": len(messages),
        "completion_state": record["completion_state"],
        "integrity_scope": "LOCAL_HASH_ONLY",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--session-root", type=Path, default=Path.home() / ".codex" / "sessions")
    parser.add_argument("--session-file", type=Path)
    parser.add_argument("--living-project-file", type=Path)
    parser.add_argument("--record-input", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args(argv)
    try:
        workspace = args.workspace.resolve()
        session = args.session_file.resolve() if args.session_file else discover_session(args.session_root, workspace)
        living = args.living_project_file.resolve() if args.living_project_file else find_living_file(workspace)
        record_input = args.record_input.resolve() if args.record_input else workspace / ".v550-agent2" / "review-record-input.json"
        output = (args.output_root or workspace / "V550 Agent 2 Review Bundles").resolve()
        output.mkdir(parents=True, exist_ok=True)
        result = create_bundle(session, workspace, living, record_input, output)
    except (BundleError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

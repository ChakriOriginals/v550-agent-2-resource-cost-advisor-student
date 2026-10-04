#!/usr/bin/env python3
"""Verify a V550 Agent 2 local review-bundle folder or ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

REQUIRED = {
    "V550_AGENT2_REVIEW_SHEET.html",
    "V550_AGENT2_REVIEW_RECORD.json",
    "V550_AGENT2_LIVING_PROJECT_FILE.md",
    "V550_AGENT2_REVIEW_MANIFEST.json",
    "README.txt",
}
MANIFEST_NAME = "V550_AGENT2_REVIEW_MANIFEST.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as handle:
        names = handle.namelist()
        if set(names) != REQUIRED:
            raise ValueError("The ZIP must contain exactly the five standardized Agent 2 review files.")
        for info in handle.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or len(member.parts) != 1 or "\\" in info.filename:
                raise ValueError("The ZIP contains an unsafe path.")
            if info.file_size > 50 * 1024 * 1024:
                raise ValueError("The ZIP contains an oversized review file.")
        handle.extractall(destination)
    return destination


def verify_directory(directory: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings = ["Local hashes detect changes but do not prove authorship without an instructor-controlled signature."]
    actual = {item.name for item in directory.iterdir() if item.is_file()}
    if actual != REQUIRED:
        missing = REQUIRED - actual
        unexpected = actual - REQUIRED
        if missing:
            errors.append("Missing required files: " + ", ".join(sorted(missing)))
        if unexpected:
            errors.append("Unexpected files: " + ", ".join(sorted(unexpected)))
        return {"valid": False, "errors": errors, "warnings": warnings}
    try:
        manifest = json.loads((directory / "V550_AGENT2_REVIEW_MANIFEST.json").read_text(encoding="utf-8"))
        record = json.loads((directory / "V550_AGENT2_REVIEW_RECORD.json").read_text(encoding="utf-8"))
        living = (directory / "V550_AGENT2_LIVING_PROJECT_FILE.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [f"Cannot read review files: {exc}"], "warnings": warnings}
    if manifest.get("schema_version") != "2.0.0" or record.get("schema_version") != "2.0.0":
        errors.append("Unsupported review-bundle schema version.")
    if manifest.get("document_type") != "V550_AGENT2_LOCAL_REVIEW_BUNDLE" or record.get("document_type") != "V550_AGENT2_LOCAL_REVIEW_BUNDLE":
        errors.append("Unexpected document type.")
    if manifest.get("integrity_scope") != "LOCAL_HASH_ONLY" or record.get("integrity_scope") != "LOCAL_HASH_ONLY":
        errors.append("Local-only integrity disclosure is missing.")
    generator = Path(__file__).with_name("generate_review_bundle.py")
    if not generator.is_file() or manifest.get("generator_sha256") != sha256_file(generator):
        errors.append("Generator hash does not match this package version.")
    declared = manifest.get("files")
    if not isinstance(declared, dict) or set(declared) != REQUIRED:
        errors.append("Manifest must inventory all five standardized files.")
    else:
        for name in REQUIRED - {MANIFEST_NAME}:
            entry = declared.get(name)
            path = directory / name
            if not isinstance(entry, dict):
                errors.append(f"Missing manifest entry for {name}.")
                continue
            if entry.get("sha256") != sha256_file(path):
                errors.append(f"Hash mismatch: {name}.")
            if entry.get("bytes") != path.stat().st_size:
                errors.append(f"Byte-length mismatch: {name}.")
        self_entry = declared.get(MANIFEST_NAME)
        if not isinstance(self_entry, dict):
            errors.append("Manifest self-entry is missing.")
        else:
            basis = dict(manifest)
            basis["files"] = {name: entry for name, entry in declared.items() if name != MANIFEST_NAME}
            canonical = (json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            if self_entry.get("sha256") != hashlib.sha256(canonical).hexdigest():
                errors.append("Manifest canonical self-basis hash mismatch.")
            if self_entry.get("bytes") != (directory / MANIFEST_NAME).stat().st_size:
                errors.append("Byte-length mismatch: manifest.")
    transcript = record.get("transcript")
    if not isinstance(transcript, list) or not transcript:
        errors.append("Visible transcript is empty or malformed.")
    else:
        for expected, message in enumerate(transcript, start=1):
            if not isinstance(message, dict) or message.get("sequence") != expected:
                errors.append("Transcript sequence is not contiguous."); break
            if message.get("role") not in {"user", "assistant"} or not isinstance(message.get("text"), str):
                errors.append("Transcript contains a non-visible role or malformed message."); break
    review = record.get("final_learning_review")
    if not isinstance(review, str) or "## V550 Stage 2 Final Learning Review" not in review:
        errors.append("The standardized Stage 2 final learning review is missing.")
    if "# V550 Agent 2 Living Project File" not in living:
        errors.append("Living Project File is missing or malformed.")
    if record.get("source_wbs_sha256") != manifest.get("source_wbs_sha256"):
        errors.append("Source-WBS hash differs between record and manifest.")
    if not isinstance(record.get("structured_work"), dict):
        errors.append("Canonical structured work is missing.")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        target = args.bundle.resolve()
        if target.is_dir():
            result = verify_directory(target)
        elif target.is_file() and target.suffix.casefold() == ".zip":
            with tempfile.TemporaryDirectory() as temporary:
                result = verify_directory(safe_extract(target, Path(temporary)))
        else:
            raise ValueError("Bundle must be a directory or ZIP file.")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        result = {"valid": False, "errors": [str(exc)], "warnings": []}
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail closed when the public V550 Agent 2 package crosses its local student boundary."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "v550-agent-2-resource-cost-advisor-student"
REQUIRED = (
    ROOT / "README.md", ROOT / "SECURITY.md", ROOT / "STUDENT_SETUP_GUIDE.md", ROOT / "install.py",
    ROOT / "start-v550.sh", ROOT / "start-v550-desktop.sh", SKILL / "SKILL.md", SKILL / "agents" / "openai.yaml",
    SKILL / "scripts" / "cost_engine.py", SKILL / "scripts" / "stage2_readiness.py",
    SKILL / "scripts" / "normalize_wbs_handoff.py", SKILL / "scripts" / "update_living_project_file.py",
    SKILL / "scripts" / "generate_review_bundle.py", SKILL / "scripts" / "verify_review_bundle.py",
    SKILL / "scripts" / "verify_canonical_knowledge.py", SKILL / "references" / "canonical-source-manifest.json",
)
FORBIDDEN_PARTS = {"backend", "dashboard", "grading", "instructor-workbook", "source-material", "telemetry"}
FORBIDDEN_SUFFIXES = {".docx", ".xlsx", ".pptx", ".pem", ".key", ".p12", ".env"}
REMOVED_MARKERS = (
    "V550_ACTION_ENDPOINT", "V550_STUDENT_KEY", "CLASS_DEPLOYMENT_TOKEN", "ACTIVE_STUDENT_KEYS_JSON",
    "REPORT_HMAC_SECRET", "startSession", "logEvent", "closeSession", "issueReport",
    "script.google.com/macros/s/", "openapi:", "studentKey", "classToken",
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]"),
)
PERSONAL_PATHS = (re.compile(r"/Users/[^/\s]+"), re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+"))


def main() -> int:
    errors: list[str] = []
    for required in REQUIRED:
        if not required.is_file():
            errors.append(f"missing required file: {required.relative_to(ROOT)}")
    files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts]
    for path in files:
        relative = path.relative_to(ROOT)
        lowered_parts = {part.casefold() for part in relative.parts}
        if FORBIDDEN_PARTS.intersection(lowered_parts):
            errors.append(f"forbidden architecture path: {relative}")
        if path.suffix.casefold() in FORBIDDEN_SUFFIXES or path.name.startswith(".env"):
            errors.append(f"forbidden public file type or credential file: {relative}")
        if path.suffix.casefold() not in {".md", ".py", ".sh", ".yaml", ".yml", ".json", ".txt"} and path.name != ".gitignore":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"non-UTF-8 public text file: {relative}"); continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret value in: {relative}")
        if path.resolve() != Path(__file__).resolve():
            for marker in REMOVED_MARKERS:
                if marker in text:
                    errors.append(f"removed runtime marker {marker!r} in: {relative}")
            for pattern in PERSONAL_PATHS:
                if pattern.search(text):
                    errors.append(f"personal filesystem path in: {relative}")
    for script in ROOT.rglob("*.py"):
        if ".git" in script.parts or "__pycache__" in script.parts:
            continue
        try:
            ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
        except (SyntaxError, UnicodeDecodeError) as exc:
            errors.append(f"Python syntax failed for {script.relative_to(ROOT)}: {exc}")
    skill_text = SKILL.joinpath("SKILL.md").read_text(encoding="utf-8") if SKILL.joinpath("SKILL.md").is_file() else ""
    if "name: v550-agent-2-resource-cost-advisor-student" not in skill_text:
        errors.append("skill frontmatter name is invalid")
    if errors:
        print("STUDENT PACKAGE CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"STUDENT PACKAGE CHECK PASSED: {len(files)} files scanned")
    print("No remote runtime, instructor-only path, credential file, secret value, or personal path was found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


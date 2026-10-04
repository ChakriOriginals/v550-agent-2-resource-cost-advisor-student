#!/usr/bin/env python3
"""Install the bundled local V550 Agent 2 skill without replacing an existing copy."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL_NAME = "v550-agent-2-resource-cost-advisor-student"
SOURCE = ROOT / "skills" / SKILL_NAME


def target_root() -> Path:
    configured = os.environ.get("V550_SKILLS_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".agents" / "skills"


def main() -> int:
    if not (SOURCE / "SKILL.md").is_file():
        print("Install failed: the bundled skill is incomplete.", file=sys.stderr)
        return 2
    destination = target_root() / SKILL_NAME
    if destination.exists():
        print(
            f"Install stopped: {destination} already exists. Move it aside only after "
            "deciding you no longer need that installation, then rerun this installer.",
            file=sys.stderr,
        )
        return 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, destination)
    print(f"Installed {SKILL_NAME} at {destination}")
    print("No course credential or external service is required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


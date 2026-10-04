#!/usr/bin/env python3
"""Run the deterministic V550 Stage 2 formal readiness review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cost_engine import evaluate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--ready", action="store_true", help="Confirm that the student explicitly requested formal review")
    args = parser.parse_args(argv)
    if not args.ready:
        print(json.dumps({"review_run": False, "error": "Formal review requires an explicit student ready signal."}))
        return 2
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        result = evaluate(packet)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"review_run": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    output = {
        "review_run": True,
        "stage": "Resource and Cost Advisor",
        "ready_to_submit": result["readiness"]["status"],
        "hard_blockers": result["readiness"]["hard_blockers"],
        "advisory_flags": result["readiness"]["advisory_flags"],
        "calculations": result["calculations"],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


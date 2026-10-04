#!/usr/bin/env python3
"""Run a fabricated local calculation, readiness, save/resume, install, and bundle flow."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from support import ROOT, SCRIPTS, complete_packet
from test_review_bundle import write_session


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, **kwargs)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout + completed.stderr)
    return completed


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        workspace = base / "workspace"
        workspace.mkdir()
        packet_path = base / "synthetic-packet.json"
        result_path = base / "engine-result.json"
        packet_path.write_text(json.dumps(complete_packet()), encoding="utf-8")
        run(["python3", str(SCRIPTS / "cost_engine.py"), str(packet_path), "--output", str(result_path)])
        review = json.loads(run(["python3", str(SCRIPTS / "stage2_readiness.py"), str(packet_path), "--ready"]).stdout)
        if review["ready_to_submit"] != "YES":
            raise RuntimeError("Synthetic complete packet did not reach readiness.")
        work_root = workspace / "V550 Agent 2 Work"
        saved = json.loads(run(["python3", str(SCRIPTS / "update_living_project_file.py"), str(packet_path), str(result_path), "--output-root", str(work_root)]).stdout)
        living = Path(saved["path"])
        lineage = "a" * 64
        resumed = json.loads(run(["python3", str(SCRIPTS / "normalize_wbs_handoff.py"), str(living), "--expected-source-sha256", lineage]).stdout)
        if not resumed["resume_metadata"]["lineage_verified"]:
            raise RuntimeError("Living Project File lineage was not verified.")
        session = base / "rollout-synthetic.jsonl"
        write_session(session, workspace)
        record_input = workspace / ".v550-agent2" / "review-record-input.json"
        record_input.parent.mkdir(parents=True)
        record_input.write_text(json.dumps({"packet": complete_packet(), "engine_result": json.loads(result_path.read_text(encoding="utf-8"))}), encoding="utf-8")
        bundle = json.loads(run([
            "python3", str(SCRIPTS / "generate_review_bundle.py"), "--workspace", str(workspace),
            "--session-file", str(session), "--living-project-file", str(living),
            "--record-input", str(record_input),
        ]).stdout)
        verified = json.loads(run(["python3", str(SCRIPTS / "verify_review_bundle.py"), bundle["archive"]]).stdout)
        install_root = base / "installed-skills"
        environment = os.environ.copy()
        environment["V550_SKILLS_HOME"] = str(install_root)
        run(["python3", str(ROOT / "install.py")], cwd=ROOT, env=environment)
        installed = (install_root / "v550-agent-2-resource-cost-advisor-student" / "SKILL.md").is_file()
        print(json.dumps({
            "synthetic_only": True,
            "ready_to_submit": review["ready_to_submit"],
            "living_project_file_saved": living.is_file(),
            "resume_lineage_verified": resumed["resume_metadata"]["lineage_verified"],
            "review_bundle_valid": verified["valid"],
            "review_bundle_completion_state": bundle["completion_state"],
            "isolated_install_succeeded": installed,
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


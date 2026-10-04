from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import ROOT, SCRIPTS, complete_packet, load_script

engine = load_script("cost_engine")


class InstallAndPackageTests(unittest.TestCase):
    def test_installer_uses_isolated_agents_skill_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / ".agents" / "skills"
            env = os.environ.copy(); env["V550_SKILLS_HOME"] = str(target)
            completed = subprocess.run(["python3", str(ROOT / "install.py")], cwd=ROOT, env=env, capture_output=True, text=True)
            installed = target / "v550-agent-2-resource-cost-advisor-student"
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "scripts" / "cost_engine.py").is_file())

    def test_installer_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "skills"; destination = target / "v550-agent-2-resource-cost-advisor-student"
            destination.mkdir(parents=True); marker = destination / "keep.txt"; marker.write_text("keep", encoding="utf-8")
            env = os.environ.copy(); env["V550_SKILLS_HOME"] = str(target)
            completed = subprocess.run(["python3", str(ROOT / "install.py")], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_launchers_have_valid_shell_syntax(self):
        for name in ("start-v550.sh", "start-v550-desktop.sh"):
            completed = subprocess.run(["sh", "-n", str(ROOT / name)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_cli_launcher_starts_in_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            fake = Path(temporary) / "codex"
            fake.write_text("#!/bin/sh\nprintf '%s' \"$PWD\"\n", encoding="utf-8"); fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy(); env["V550_CODEX_CLI"] = str(fake)
            completed = subprocess.run([str(ROOT / "start-v550.sh")], cwd=ROOT.parent, env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, str(ROOT))

    def test_package_scanner_passes(self):
        completed = subprocess.run(["python3", str(ROOT / "tools" / "verify_package.py")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout)

    def test_canonical_verifier_passes(self):
        completed = subprocess.run(["python3", str(SCRIPTS / "verify_canonical_knowledge.py"), "--repo-root", str(ROOT)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertTrue(json.loads(completed.stdout)["valid"])

    def test_living_project_file_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); packet_path = base / "packet.json"; result_path = base / "result.json"
            packet = complete_packet(); packet_path.write_text(json.dumps(packet), encoding="utf-8")
            result_path.write_text(json.dumps(engine.evaluate(packet)), encoding="utf-8")
            completed = subprocess.run(["python3", str(SCRIPTS / "update_living_project_file.py"), str(packet_path), str(result_path), "--output-root", str(base / "work")], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout)
            living = Path(json.loads(completed.stdout)["path"])
            normalized = subprocess.run(["python3", str(SCRIPTS / "normalize_wbs_handoff.py"), str(living)], capture_output=True, text=True)
        self.assertEqual(normalized.returncode, 0, normalized.stdout)
        self.assertEqual(json.loads(normalized.stdout)["approved_wbs"][0]["wbs_id"], "WP-1")

    def test_stage2_review_requires_explicit_ready_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet = Path(temporary) / "packet.json"; packet.write_text(json.dumps(complete_packet()), encoding="utf-8")
            blocked = subprocess.run(["python3", str(SCRIPTS / "stage2_readiness.py"), str(packet)], capture_output=True, text=True)
            allowed = subprocess.run(["python3", str(SCRIPTS / "stage2_readiness.py"), str(packet), "--ready"], capture_output=True, text=True)
        self.assertEqual(blocked.returncode, 2)
        self.assertEqual(allowed.returncode, 0)
        self.assertEqual(json.loads(allowed.stdout)["ready_to_submit"], "YES")


if __name__ == "__main__":
    unittest.main()


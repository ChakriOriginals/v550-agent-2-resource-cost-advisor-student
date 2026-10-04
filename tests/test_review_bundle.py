from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from support import SCRIPTS, complete_packet, load_script

GENERATOR = SCRIPTS / "generate_review_bundle.py"
VERIFIER = SCRIPTS / "verify_review_bundle.py"
engine = load_script("cost_engine")


def event(kind: str, payload: dict, ordinal: int) -> dict:
    return {"timestamp": f"2027-01-12T12:{ordinal:02d}:00Z", "type": kind, "payload": payload}


def write_session(path: Path, workspace: Path, *, review: bool = True) -> None:
    rows = [
        event("session_meta", {"id": "synthetic-session", "cwd": str(workspace), "timestamp": "2027-01-12T12:00:00Z"}, 1),
        event("response_item", {"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "HIDDEN INSTRUCTION"}]}, 2),
        event("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "I am ready for review"}]}, 3),
        event("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Stage: Resource and Cost Advisor\nReady to submit: YES"}]}, 4),
    ]
    if review:
        rows.extend([
            event("response_item", {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "## V550 Stage 2 Final Learning Review\n\nCompletion state: ready.\nDemonstrated learning: the synthetic plan reconciles."}]}, 5),
            event("response_item", {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Generate my review bundle"}]}, 6),
        ])
    path.write_text("".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8")


class ReviewBundleTests(unittest.TestCase):
    def generate(self, temporary: str, *, review: bool = True):
        base = Path(temporary); workspace = base / "workspace"; workspace.mkdir()
        session = base / "rollout-synthetic.jsonl"; write_session(session, workspace, review=review)
        packet = complete_packet(); result = engine.evaluate(packet)
        record_input = base / "review-input.json"
        record_input.write_text(json.dumps({"packet": packet, "engine_result": result}), encoding="utf-8")
        living = base / "living.md"
        living.write_text("# V550 Agent 2 Living Project File\n\nSynthetic data only.\n", encoding="utf-8")
        output = base / "output"
        completed = subprocess.run([
            "python3", str(GENERATOR), "--workspace", str(workspace), "--session-file", str(session),
            "--living-project-file", str(living), "--record-input", str(record_input), "--output-root", str(output),
        ], capture_output=True, text=True)
        return completed, output

    def test_generates_exact_five_files_and_valid_zip(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, _ = self.generate(temporary)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout); bundle = Path(result["bundle_directory"])
            self.assertEqual({item.name for item in bundle.iterdir()}, {
                "V550_AGENT2_REVIEW_SHEET.html", "V550_AGENT2_REVIEW_RECORD.json",
                "V550_AGENT2_LIVING_PROJECT_FILE.md", "V550_AGENT2_REVIEW_MANIFEST.json", "README.txt",
            })
            manifest = json.loads((bundle / "V550_AGENT2_REVIEW_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(set(manifest["files"]), {item.name for item in bundle.iterdir()})
            verified = subprocess.run(["python3", str(VERIFIER), result["archive"]], capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stdout)
            self.assertTrue(json.loads(verified.stdout)["valid"])

    def test_visible_transcript_excludes_hidden_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, _ = self.generate(temporary); data = json.loads(completed.stdout)
            record = json.loads((Path(data["bundle_directory"]) / "V550_AGENT2_REVIEW_RECORD.json").read_text(encoding="utf-8"))
        rendered = " ".join(item["text"] for item in record["transcript"])
        self.assertIn("I am ready for review", rendered)
        self.assertNotIn("HIDDEN INSTRUCTION", rendered)
        self.assertEqual({item["role"] for item in record["transcript"]}, {"user", "assistant"})

    def test_missing_final_review_prevents_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, _ = self.generate(temporary, review=False)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("final learning review", completed.stdout)

    def test_tampered_file_fails_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, _ = self.generate(temporary); bundle = Path(json.loads(completed.stdout)["bundle_directory"])
            bundle.chmod(0o755); sheet = bundle / "V550_AGENT2_REVIEW_SHEET.html"; sheet.chmod(0o644)
            sheet.write_text(sheet.read_text(encoding="utf-8") + "tampered", encoding="utf-8")
            verified = subprocess.run(["python3", str(VERIFIER), str(bundle)], capture_output=True, text=True)
        self.assertEqual(verified.returncode, 1)
        self.assertIn("Hash mismatch", verified.stdout)

    def test_bundle_payload_files_are_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed, _ = self.generate(temporary); bundle = Path(json.loads(completed.stdout)["bundle_directory"])
            modes = [os.stat(path).st_mode for path in bundle.iterdir()]
        self.assertTrue(all(not mode & stat.S_IWUSR for mode in modes))

    def test_unsafe_archive_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../V550_AGENT2_REVIEW_RECORD.json", "{}")
            verified = subprocess.run(["python3", str(VERIFIER), str(archive)], capture_output=True, text=True)
        self.assertEqual(verified.returncode, 1)
        self.assertFalse(json.loads(verified.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()

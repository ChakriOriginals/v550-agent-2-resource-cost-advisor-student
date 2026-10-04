from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from support import ROOT, SCRIPTS, complete_packet, load_script

engine = load_script("cost_engine")


class CostEngineTests(unittest.TestCase):
    def test_complete_packet_is_ready_and_reconciles(self):
        result = engine.evaluate(complete_packet())
        self.assertTrue(result["readiness"]["ready"], result["readiness"])
        self.assertTrue(result["calculations"]["reconciles"])

    def test_fixed_labor_rates_are_applied(self):
        result = engine.evaluate(complete_packet())
        wp1 = next(row for row in result["calculations"]["labor_lines"] if row["wbs_id"] == "WP-1")
        self.assertEqual(wp1["rate"], "43")
        self.assertEqual(wp1["unrounded_labor_value"], "430")

    def test_cash_uses_fixed_costs_and_software_minimum(self):
        result = engine.evaluate(complete_packet())
        software = next(row for row in result["calculations"]["cash_lines"] if row["category"].startswith("ROOM_"))
        self.assertEqual(software["entered_quantity"], "1")
        self.assertEqual(software["billed_quantity"], "12")
        self.assertEqual(result["calculations"]["cash_total_unrounded"], "5000")

    def test_labor_is_not_added_to_cash(self):
        result = engine.evaluate(complete_packet())
        self.assertEqual(result["calculations"]["cash_total_unrounded"], "5000")
        self.assertNotEqual(result["calculations"]["labor_total_unrounded"], "5000")

    def test_pert_rounds_up_to_half_hour(self):
        result = engine.evaluate(complete_packet())
        wp1 = result["calculations"]["uncertainty_packages"][0]
        self.assertEqual(wp1["expected_hours_unrounded"], "10.33333333333333333333333333")
        self.assertEqual(wp1["expected_hours_rounded_up"], "10.5")

    def test_contingency_bounds(self):
        result = engine.evaluate(complete_packet())
        self.assertEqual(result["calculations"]["contingency_min_hours"], "1.5")
        self.assertEqual(result["calculations"]["contingency_max_hours"], "13")

    def test_out_of_range_contingency_blocks(self):
        packet = complete_packet(); packet["contingency"]["hours"] = 14
        codes = {item["code"] for item in engine.evaluate(packet)["readiness"]["hard_blockers"]}
        self.assertIn("CONTINGENCY_RANGE", codes)

    def test_facilitator_half_day_rule(self):
        packet = complete_packet(); packet["cash_lines"][0]["quantity"] = 1.25
        codes = {item["code"] for item in engine.evaluate(packet)["readiness"]["hard_blockers"]}
        self.assertIn("FACILITATOR_INCREMENT", codes)

    def test_staff_or_board_stipend_is_rejected(self):
        packet = complete_packet(); packet["cash_lines"][1]["participant_type"] = "BOARD"
        codes = {item["code"] for item in engine.evaluate(packet)["readiness"]["hard_blockers"]}
        self.assertIn("STIPEND_ELIGIBILITY", codes)

    def test_excluded_cash_category_blocks(self):
        packet = complete_packet(); packet["cash_lines"].append({"category": "CATERING", "quantity": 1})
        codes = {item["code"] for item in engine.evaluate(packet)["readiness"]["hard_blockers"]}
        self.assertIn("EXCLUDED_CASH_CATEGORY", codes)

    def test_cash_ceiling_blocks(self):
        packet = complete_packet(); packet["cash_lines"][0]["quantity"] = 30
        codes = {item["code"] for item in engine.evaluate(packet)["readiness"]["hard_blockers"]}
        self.assertIn("CASH_CEILING", codes)

    def test_pre_vote_ceiling_blocks(self):
        packet = complete_packet()
        packet["estimates"][0]["most_likely_hours"] = 520
        packet["uncertainty_packages"][0] = {"wbs_id": "WP-1", "optimistic_hours": 520, "most_likely_hours": 520, "pessimistic_hours": 520}
        packet["contingency"]["hours"] = 1
        codes = {item["code"] for item in engine.evaluate(packet)["readiness"]["hard_blockers"]}
        self.assertIn("PRE_VOTE_CEILING", codes)

    def test_post_vote_ceiling_blocks(self):
        packet = complete_packet(); packet["estimates"][3]["most_likely_hours"] = 66
        codes = {item["code"] for item in engine.evaluate(packet)["readiness"]["hard_blockers"]}
        self.assertIn("POST_VOTE_CEILING", codes)

    def test_exact_source_capacity_windows(self):
        self.assertEqual(engine.paper_capacity(date(2027, 1, 12), date(2027, 2, 6), "Marcus Feld")[0], Decimal("56"))
        self.assertEqual(engine.paper_capacity(date(2027, 5, 15), date(2027, 6, 1), "Priya Raghavan")[0], Decimal("17.5"))

    def test_milestones_and_calendar_match_scenario_2(self):
        self.assertEqual(engine.MILESTONES["COMMITTEE_MATERIALS_DUE"], "2027-03-12")
        self.assertEqual(engine.MILESTONES["BOARD_PACKET_DUE"], "2027-05-07")
        self.assertEqual(engine.MILESTONES["SEASON_ANNOUNCEMENT_AND_COMPLETE"], "2027-06-01")
        self.assertEqual(len(engine.CALENDAR_FACTS), 13)
        self.assertIn(("2027-04-17", "2027-05-23", "Peak rentals: nine weekend recitals and graduations", "Marcus Feld"), engine.CALENDAR_FACTS)
        self.assertEqual(engine.LEAD_TIMES["Gwen Tsai written lease question"], "10 business days")

    def test_pre_post_timing_mismatch_blocks(self):
        packet = complete_packet(); packet["approved_wbs"][3]["timing_label"] = "PRE_VOTE"
        codes = {item["code"] for item in engine.evaluate(packet)["readiness"]["hard_blockers"]}
        self.assertIn("TIMING_PHASE_MISMATCH", codes)

    def test_realistic_pressure_is_advisory_and_requires_reason_to_accept(self):
        packet = complete_packet(); packet["realistic_capacity"][0]["hours"] = 5
        result = engine.evaluate(packet)
        self.assertFalse(result["readiness"]["ready"])
        packet["accepted_flags"] = [{"code": "REALISTIC_CAPACITY_PRESSURE", "reason": "Student accepts this noncritical pressure after calendar review."}]
        self.assertTrue(engine.evaluate(packet)["readiness"]["ready"])

    def test_deterministic_runs_are_identical(self):
        packet = complete_packet()
        self.assertEqual(engine.evaluate(packet), engine.evaluate(packet))

    def test_cli_writes_same_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet_path = Path(temporary) / "packet.json"
            packet_path.write_text(json.dumps(complete_packet()), encoding="utf-8")
            completed = subprocess.run(["python3", str(SCRIPTS / "cost_engine.py"), str(packet_path)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["readiness"]["ready"])


if __name__ == "__main__":
    unittest.main()

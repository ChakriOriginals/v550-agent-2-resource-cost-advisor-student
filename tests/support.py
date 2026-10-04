from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "v550-agent-2-resource-cost-advisor-student" / "scripts"


def load_script(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_v550_script_{name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def complete_packet() -> dict:
    packet = {
        "schema_version": "2.0.0",
        "project": {
            "title": "Synthetic Facilities Plan",
            "source_wbs_filename": "synthetic-approved-wbs.json",
            "source_wbs_sha256": "a" * 64,
            "source_wbs_version": "1.0",
            "deliverables": ["D-1", "D-2", "D-3", "D-4"],
        },
        "phases": [
            {"phase_id": "P1", "name": "Consult", "start_date": "2027-01-12", "end_date": "2027-03-19"},
            {"phase_id": "P2", "name": "Recommend", "start_date": "2027-03-20", "end_date": "2027-05-14"},
            {"phase_id": "P3", "name": "Close", "start_date": "2027-05-15", "end_date": "2027-06-01"},
        ],
        "approved_wbs": [
            {"wbs_id": "WP-1", "title": "Consultation plan", "parent_id": "1", "deliverable_id": "D-1", "scope_status": "APPROVED", "timing_label": "PRE_VOTE", "phase_id": "P1", "owner": "Marcus Feld"},
            {"wbs_id": "WP-2", "title": "Space evidence", "parent_id": "1", "deliverable_id": "D-2", "scope_status": "APPROVED", "timing_label": "PRE_VOTE", "phase_id": "P1", "owner": "Priya Raghavan"},
            {"wbs_id": "WP-3", "title": "Allocation draft", "parent_id": "2", "deliverable_id": "D-3", "scope_status": "APPROVED", "timing_label": "PRE_VOTE", "phase_id": "P2", "owner": "Tomas Beltrán"},
            {"wbs_id": "WP-4", "title": "Announcement handoff", "parent_id": "3", "deliverable_id": "D-4", "scope_status": "APPROVED", "timing_label": "POST_VOTE", "phase_id": "P3", "owner": "Marcus Feld"},
        ],
        "realistic_capacity": [
            {"phase_id": phase, "resource": person, "hours": hours, "reason": "Calendar reviewed for synthetic test."}
            for phase, values in {
                "P1": {"Marcus Feld": 100, "Priya Raghavan": 50, "Tomas Beltrán": 35},
                "P2": {"Marcus Feld": 90, "Priya Raghavan": 50, "Tomas Beltrán": 35},
                "P3": {"Marcus Feld": 25, "Priya Raghavan": 12, "Tomas Beltrán": 10},
            }.items() for person, hours in values.items()
        ],
        "estimates": [
            {"wbs_id": "WP-1", "most_likely_hours": 10, "method": "BOTTOM_UP", "evidence": "Synthetic task list."},
            {"wbs_id": "WP-2", "most_likely_hours": 8, "method": "ANALOGOUS", "evidence": "Synthetic comparison."},
            {"wbs_id": "WP-3", "most_likely_hours": 12, "method": "EXPERT_JUDGMENT", "evidence": "Synthetic team judgment."},
            {"wbs_id": "WP-4", "most_likely_hours": 6, "method": "PARAMETRIC", "evidence": "Synthetic quantity assumption."},
        ],
        "cash_lines": [
            {"line_id": "C1", "category": "FACILITATOR_DAY", "quantity": 1.5, "reason": "Workshop"},
            {"line_id": "C2", "category": "OUTSIDE_PARTICIPANT_STIPEND", "quantity": 10, "participant_type": "OUTSIDE", "reason": "Outside sessions"},
            {"line_id": "C3", "category": "ROOM_SCHEDULING_SOFTWARE_MONTH", "quantity": 1, "reason": "Planning access"},
            {"line_id": "C4", "category": "PRINT_BW_PAGE", "quantity": 100, "reason": "Drafts"},
            {"line_id": "C5", "category": "PRINT_COLOR_PAGE", "quantity": 20, "reason": "Board packet"},
            {"line_id": "C6", "category": "LARGE_FORMAT_FLOOR_PLAN", "quantity": 2, "reason": "Meetings"},
        ],
        "cash_contingency": 0,
        "uncertainty_packages": [
            {"wbs_id": "WP-1", "optimistic_hours": 8, "most_likely_hours": 10, "pessimistic_hours": 14},
            {"wbs_id": "WP-2", "optimistic_hours": 6, "most_likely_hours": 8, "pessimistic_hours": 11},
            {"wbs_id": "WP-3", "optimistic_hours": 9, "most_likely_hours": 12, "pessimistic_hours": 18},
        ],
        "contingency": {"hours": 3, "holder": "Marcus Feld", "phase_id": "P2", "justification": "Near the lower bound because inputs are already documented."},
        "conflicts": [], "wbs_corrections": [], "scope_changes": [], "accepted_flags": [],
        "assumptions": ["Synthetic only"], "tradeoffs": ["Synthetic only"], "limitations": ["Synthetic only"],
        "final_explanation": "This fabricated plan separates labor value from cash and explains the selected contingency.",
        "revisions": [],
    }
    return copy.deepcopy(packet)

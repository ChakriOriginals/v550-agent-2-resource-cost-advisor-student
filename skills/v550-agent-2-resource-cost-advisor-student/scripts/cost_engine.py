#!/usr/bin/env python3
"""Deterministic V550 Agent 2 labor, cash, capacity, and readiness engine."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP, getcontext
from pathlib import Path
from typing import Any

getcontext().prec = 28

SCHEMA_VERSION = "2.0.0"
RATE_TABLE_VERSION = "1.0"
RATE_TABLE_APPROVED = "2027-01-05"
PROJECT_START = date(2027, 1, 12)
VOTE_DATE = date(2027, 5, 14)
POST_START = date(2027, 5, 15)
PROJECT_END = date(2027, 6, 1)
CASH_CEILING = Decimal("35000")
PRE_VOTE_CEILING = Decimal("525")
POST_VOTE_CEILING = Decimal("65.5")

RATES = {
    "Marcus Feld": Decimal("43"),
    "Priya Raghavan": Decimal("34"),
    "Tomas Beltrán": Decimal("36"),
}
WEEKLY_CAPACITY = {
    "Marcus Feld": Decimal("16"),
    "Priya Raghavan": Decimal("8"),
    "Tomas Beltrán": Decimal("6"),
}
EXACT_CAPACITY = {
    (date(2027, 1, 12), date(2027, 2, 6)): {
        "Marcus Feld": Decimal("56"), "Priya Raghavan": Decimal("28"), "Tomas Beltrán": Decimal("21")
    },
    (date(2027, 2, 7), date(2027, 3, 19)): {
        "Marcus Feld": Decimal("96"), "Priya Raghavan": Decimal("48"), "Tomas Beltrán": Decimal("36")
    },
    (date(2027, 3, 20), date(2027, 5, 14)): {
        "Marcus Feld": Decimal("128"), "Priya Raghavan": Decimal("64"), "Tomas Beltrán": Decimal("48")
    },
    (date(2027, 1, 12), date(2027, 5, 14)): {
        "Marcus Feld": Decimal("280"), "Priya Raghavan": Decimal("140"), "Tomas Beltrán": Decimal("105")
    },
    (date(2027, 5, 15), date(2027, 6, 1)): {
        "Marcus Feld": Decimal("35"), "Priya Raghavan": Decimal("17.5"), "Tomas Beltrán": Decimal("13")
    },
}
METHODS = {"EXPERT_JUDGMENT", "ANALOGOUS", "PARAMETRIC", "BOTTOM_UP", "THREE_POINT"}
CASH_RULES = {
    "FACILITATOR_DAY": Decimal("1200"),
    "OUTSIDE_PARTICIPANT_STIPEND": Decimal("75"),
    "ROOM_SCHEDULING_SOFTWARE_MONTH": Decimal("200"),
    "PRINT_BW_PAGE": Decimal("0.10"),
    "PRINT_COLOR_PAGE": Decimal("0.50"),
    "LARGE_FORMAT_FLOOR_PLAN": Decimal("15"),
}
MILESTONES = {
    "KICKOFF": "2027-01-12",
    "COMMITTEE_MATERIALS_DUE": "2027-03-12",
    "COMMITTEE_UPDATE": "2027-03-19",
    "BOARD_PACKET_DUE": "2027-05-07",
    "BOARD_VOTE": "2027-05-14",
    "MEMORIAL_DAY_CLOSED": "2027-05-31",
    "SEASON_ANNOUNCEMENT_AND_COMPLETE": "2027-06-01",
}
CALENDAR_FACTS = (
    ("2027-01-18", "2027-01-18", "Martin Luther King Jr. Day closure", "Everyone"),
    ("2027-01-19", "2027-04-24", "Priya teaches Monday and Wednesday 4–6 p.m. plus preparation", "Priya Raghavan"),
    ("2027-01-22", "2027-01-28", "Mainstage Show 3 tech week", "Tomas Beltrán heavily; Marcus Feld"),
    ("2027-01-29", "2027-02-14", "Show 3 performances Thursday–Sunday", "Marcus Feld; Tomas Beltrán"),
    ("2027-03-05", "2027-03-11", "Mainstage Show 4 tech week", "Tomas Beltrán heavily; Marcus Feld"),
    ("2027-03-12", "2027-03-28", "Show 4 performances Thursday–Sunday", "Marcus Feld; Tomas Beltrán"),
    ("2027-03-15", "2027-03-19", "Learning and Media spring break", "Priya Raghavan"),
    ("2027-03-31", "2027-03-31", "Building maintenance contract renewal due", "Marcus Feld"),
    ("2027-04-08", "2027-04-18", "New Play Development spring festival", "Marcus Feld; Tomas Beltrán"),
    ("2027-04-17", "2027-05-23", "Peak rentals: nine weekend recitals and graduations", "Marcus Feld"),
    ("2027-04-23", "2027-04-29", "Mainstage Show 5 tech week", "Tomas Beltrán heavily; Marcus Feld"),
    ("2027-04-30", "2027-05-16", "Show 5 performances Thursday–Sunday", "Marcus Feld; Tomas Beltrán"),
    ("2027-05-01", "2027-05-01", "Learning and Media spring showcase", "Priya Raghavan"),
)
LEAD_TIMES = {
    "Ruth Adeyemi email": "1 day",
    "Gwen Tsai written lease question": "10 business days",
    "Legacy-lead meeting through Dana Okoye": "1 week",
}


def dec(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{field} must be numeric")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def iso_date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD") from exc


def half_step(value: Decimal) -> bool:
    return value >= 1 and value * 2 == (value * 2).to_integral_value()


def round_up_half(value: Decimal) -> Decimal:
    return (value * 2).to_integral_value(rounding=ROUND_CEILING) / 2


def display_dollars(value: Decimal) -> str:
    return str(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def paper_capacity(start: date, end: date, person: str) -> tuple[Decimal, str]:
    exact = EXACT_CAPACITY.get((start, end))
    if exact is not None:
        return exact[person], "SCENARIO_2_FIXED_WINDOW"
    inclusive_days = Decimal((end - start).days + 1)
    value = WEEKLY_CAPACITY[person] * inclusive_days / Decimal("7")
    return value, "WEEKLY_RATE_X_INCLUSIVE_CALENDAR_DAYS_DIV_7"


def issue(code: str, message: str, path: str, *, hard: bool = True) -> dict[str, Any]:
    return {"code": code, "message": message, "path": path, "hard_blocker": hard}


def evaluate(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    wbs = packet.get("approved_wbs")
    phases = packet.get("phases")
    estimates = packet.get("estimates")
    if not isinstance(wbs, list) or not wbs:
        errors.append(issue("WBS_REQUIRED", "A non-empty normalized approved WBS is required.", "approved_wbs"))
        wbs = []
    if not isinstance(phases, list):
        errors.append(issue("PHASES_REQUIRED", "Three or four phases are required.", "phases"))
        phases = []
    if len(phases) not in {3, 4}:
        errors.append(issue("PHASE_COUNT", "Define exactly three or four phases.", "phases"))
    if not isinstance(estimates, list):
        errors.append(issue("ESTIMATES_REQUIRED", "An estimate is required for every active work package.", "estimates"))
        estimates = []

    phase_by_id: dict[str, dict[str, Any]] = {}
    phase_dates: dict[str, tuple[date, date]] = {}
    for index, phase in enumerate(phases):
        path = f"phases[{index}]"
        if not isinstance(phase, dict):
            errors.append(issue("PHASE_OBJECT", "Each phase must be an object.", path)); continue
        phase_id = phase.get("phase_id")
        if not isinstance(phase_id, str) or not phase_id:
            errors.append(issue("PHASE_ID", "Phase ID is required.", f"{path}.phase_id")); continue
        if phase_id in phase_by_id:
            errors.append(issue("DUPLICATE_PHASE_ID", f"Duplicate phase ID {phase_id!r}.", f"{path}.phase_id")); continue
        try:
            start = iso_date(phase.get("start_date"), f"{path}.start_date")
            end = iso_date(phase.get("end_date"), f"{path}.end_date")
        except ValueError as exc:
            errors.append(issue("PHASE_DATE", str(exc), path)); continue
        if start > end:
            errors.append(issue("PHASE_DATE_ORDER", "Phase start must not be after its end.", path))
        if start < PROJECT_START or end > PROJECT_END:
            errors.append(issue("PROJECT_WINDOW", "All phase work must remain between January 12 and June 1, 2027.", path))
        if start <= VOTE_DATE < end:
            errors.append(issue("PHASE_CROSSES_VOTE", "A phase cannot cross the May 14 pre/post-vote boundary.", path))
        phase_by_id[phase_id] = phase
        phase_dates[phase_id] = (start, end)
    ordered_phases = sorted(((start, end, phase_id) for phase_id, (start, end) in phase_dates.items()), key=lambda item: item[0])
    for previous, current in zip(ordered_phases, ordered_phases[1:]):
        if current[0] <= previous[1]:
            errors.append(issue("PHASE_OVERLAP", f"Phases {previous[2]} and {current[2]} overlap.", "phases"))

    wbs_by_id: dict[str, dict[str, Any]] = {}
    active_wbs: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(wbs):
        path = f"approved_wbs[{index}]"
        if not isinstance(row, dict):
            errors.append(issue("WBS_OBJECT", "Each WBS row must be an object.", path)); continue
        wbs_id = row.get("wbs_id")
        if not isinstance(wbs_id, str) or not wbs_id:
            errors.append(issue("WBS_ID", "WBS ID is required and cannot be invented.", f"{path}.wbs_id")); continue
        if wbs_id in wbs_by_id:
            errors.append(issue("DUPLICATE_WBS_ID", f"Duplicate WBS ID {wbs_id!r}.", f"{path}.wbs_id")); continue
        wbs_by_id[wbs_id] = row
        for field in ("title", "deliverable_id", "scope_status", "timing_label"):
            if not isinstance(row.get(field), str) or not row.get(field):
                errors.append(issue("WBS_FIELD", f"{field} is required and cannot be invented.", f"{path}.{field}"))
        scope_status = row.get("scope_status")
        if scope_status not in {"APPROVED", "WBS_CORRECTION", "SCOPE_CHANGE"}:
            errors.append(issue("SCOPE_STATUS", "Use APPROVED, WBS_CORRECTION, or SCOPE_CHANGE.", f"{path}.scope_status"))
        if scope_status == "WBS_CORRECTION" and not str(row.get("change_reason", "")).strip():
            errors.append(issue("CORRECTION_REASON", "A WBS correction needs a reason tied to an approved deliverable.", path))
        if scope_status == "SCOPE_CHANGE" and row.get("approval_status") != "APPROVED":
            flags.append(issue("SCOPE_CHANGE_EXCLUDED", f"{wbs_id} is excluded from approved totals until approved.", path, hard=False))
            continue
        phase_id = row.get("phase_id")
        if phase_id not in phase_by_id:
            errors.append(issue("WBS_PHASE", f"{wbs_id} must map to one valid phase.", f"{path}.phase_id"))
        owner = row.get("owner")
        if owner not in RATES:
            errors.append(issue("WBS_OWNER", f"{wbs_id} needs exactly one approved team owner.", f"{path}.owner"))
        if row.get("timing_label") not in {"PRE_VOTE", "POST_VOTE"}:
            errors.append(issue("TIMING_LABEL", f"{wbs_id} must preserve PRE_VOTE or POST_VOTE.", f"{path}.timing_label"))
        elif phase_id in phase_dates:
            phase_start, phase_end = phase_dates[phase_id]
            if row.get("timing_label") == "PRE_VOTE" and phase_start >= POST_START:
                errors.append(issue("TIMING_PHASE_MISMATCH", f"{wbs_id} is PRE_VOTE but is assigned after the vote.", path))
            if row.get("timing_label") == "POST_VOTE" and phase_end <= VOTE_DATE:
                errors.append(issue("TIMING_PHASE_MISMATCH", f"{wbs_id} is POST_VOTE but is assigned before or on the vote.", path))
        active_wbs[wbs_id] = row

    estimate_by_wbs: dict[str, dict[str, Any]] = {}
    estimate_hours: dict[str, Decimal] = {}
    for index, estimate in enumerate(estimates):
        path = f"estimates[{index}]"
        if not isinstance(estimate, dict):
            errors.append(issue("ESTIMATE_OBJECT", "Each estimate must be an object.", path)); continue
        wbs_id = estimate.get("wbs_id")
        if wbs_id in estimate_by_wbs:
            errors.append(issue("DUPLICATE_ESTIMATE", f"Duplicate estimate for {wbs_id!r}.", path)); continue
        if wbs_id not in active_wbs:
            errors.append(issue("ESTIMATE_WBS", f"Estimate references unknown or excluded WBS ID {wbs_id!r}.", f"{path}.wbs_id")); continue
        estimate_by_wbs[wbs_id] = estimate
        try:
            hours = dec(estimate.get("most_likely_hours"), f"{path}.most_likely_hours")
            if not half_step(hours):
                errors.append(issue("ESTIMATE_STEP", "Most likely hours must be at least 1 and use 0.5-hour steps.", f"{path}.most_likely_hours"))
            estimate_hours[wbs_id] = hours
        except ValueError as exc:
            errors.append(issue("ESTIMATE_HOURS", str(exc), f"{path}.most_likely_hours"))
        if estimate.get("method") not in METHODS:
            errors.append(issue("ESTIMATE_METHOD", "Use one approved estimating method label.", f"{path}.method"))
        if not str(estimate.get("evidence", "")).strip():
            errors.append(issue("ESTIMATE_EVIDENCE", "Provide evidence or a transparent assumption.", f"{path}.evidence"))
    for wbs_id in active_wbs:
        if wbs_id not in estimate_by_wbs:
            errors.append(issue("MISSING_ESTIMATE", f"Missing estimate for {wbs_id}.", f"estimates.{wbs_id}"))

    realistic_lookup: dict[tuple[str, str], Decimal] = {}
    for index, row in enumerate(packet.get("realistic_capacity", [])):
        path = f"realistic_capacity[{index}]"
        if not isinstance(row, dict):
            errors.append(issue("REALISTIC_OBJECT", "Each realistic-capacity row must be an object.", path)); continue
        key = (row.get("phase_id"), row.get("resource"))
        if key[0] not in phase_by_id or key[1] not in RATES:
            errors.append(issue("REALISTIC_KEY", "Realistic capacity needs a valid phase and team member.", path)); continue
        try:
            hours = dec(row.get("hours"), f"{path}.hours")
            if hours < 0:
                raise ValueError("realistic hours cannot be negative")
            realistic_lookup[key] = hours
        except ValueError as exc:
            errors.append(issue("REALISTIC_HOURS", str(exc), f"{path}.hours")); continue
        if not str(row.get("reason", "")).strip():
            errors.append(issue("REALISTIC_REASON", "Give a calendar-based reason for realistic capacity.", f"{path}.reason"))
    for phase_id in phase_by_id:
        for person in RATES:
            if (phase_id, person) not in realistic_lookup:
                errors.append(issue("REALISTIC_MISSING", f"Realistic capacity is missing for {person} in {phase_id}.", "realistic_capacity"))

    labor_lines: list[dict[str, Any]] = []
    totals_person = {person: Decimal("0") for person in RATES}
    totals_phase = {phase_id: Decimal("0") for phase_id in phase_by_id}
    hours_person_phase = {(phase_id, person): Decimal("0") for phase_id in phase_by_id for person in RATES}
    pre_hours = Decimal("0")
    post_hours = Decimal("0")
    for wbs_id, row in active_wbs.items():
        if wbs_id not in estimate_hours or row.get("owner") not in RATES or row.get("phase_id") not in phase_by_id:
            continue
        hours = estimate_hours[wbs_id]
        owner = row["owner"]
        phase_id = row["phase_id"]
        cost = hours * RATES[owner]
        labor_lines.append({
            "wbs_id": wbs_id, "phase_id": phase_id, "person": owner,
            "hours": decimal_text(hours), "rate": decimal_text(RATES[owner]),
            "unrounded_labor_value": decimal_text(cost), "display_labor_value": display_dollars(cost),
        })
        totals_person[owner] += cost
        totals_phase[phase_id] += cost
        hours_person_phase[(phase_id, owner)] += hours
        if row.get("timing_label") == "PRE_VOTE": pre_hours += hours
        elif row.get("timing_label") == "POST_VOTE": post_hours += hours

    cash_lines: list[dict[str, Any]] = []
    cash_total = Decimal("0")
    raw_cash = packet.get("cash_lines", [])
    if not isinstance(raw_cash, list):
        errors.append(issue("CASH_LINES", "Cash lines must be a list.", "cash_lines")); raw_cash = []
    for index, row in enumerate(raw_cash):
        path = f"cash_lines[{index}]"
        if not isinstance(row, dict):
            errors.append(issue("CASH_OBJECT", "Each cash line must be an object.", path)); continue
        category = row.get("category")
        if category not in CASH_RULES:
            errors.append(issue("EXCLUDED_CASH_CATEGORY", f"Cash category {category!r} is not approved.", f"{path}.category")); continue
        try:
            entered = dec(row.get("quantity"), f"{path}.quantity")
            if entered < 0:
                raise ValueError("quantity cannot be negative")
        except ValueError as exc:
            errors.append(issue("CASH_QUANTITY", str(exc), f"{path}.quantity")); continue
        billed = entered
        if category == "FACILITATOR_DAY" and entered * 2 != (entered * 2).to_integral_value():
            errors.append(issue("FACILITATOR_INCREMENT", "Facilitator time must use half-day increments.", f"{path}.quantity"))
        if category == "ROOM_SCHEDULING_SOFTWARE_MONTH":
            billed = max(entered, Decimal("12"))
        if category == "OUTSIDE_PARTICIPANT_STIPEND" and row.get("participant_type") != "OUTSIDE":
            errors.append(issue("STIPEND_ELIGIBILITY", "Stipends are only for outside participants, never staff or board.", path))
        if not str(row.get("reason", "")).strip():
            errors.append(issue("CASH_REASON", "Each cash quantity needs the student's reason.", f"{path}.reason"))
        cost = billed * CASH_RULES[category]
        cash_total += cost
        cash_lines.append({
            "line_id": row.get("line_id", f"CASH-{index + 1}"), "category": category,
            "entered_quantity": decimal_text(entered), "billed_quantity": decimal_text(billed),
            "unit_cost": decimal_text(CASH_RULES[category]), "unrounded_cost": decimal_text(cost),
            "display_cost": display_dollars(cost), "reason": row.get("reason", ""),
        })
    try:
        cash_contingency = dec(packet.get("cash_contingency", 0), "cash_contingency")
        if cash_contingency < 0:
            raise ValueError("cash contingency cannot be negative")
    except ValueError as exc:
        errors.append(issue("CASH_CONTINGENCY", str(exc), "cash_contingency")); cash_contingency = Decimal("0")
    cash_total_with_contingency = cash_total + cash_contingency
    if cash_total_with_contingency > CASH_CEILING:
        errors.append(issue("CASH_CEILING", "Cash cost including cash contingency exceeds $35,000.", "cash_lines"))

    uncertainty = packet.get("uncertainty_packages", [])
    if not isinstance(uncertainty, list):
        uncertainty = []
    if len(uncertainty) != 3:
        errors.append(issue("UNCERTAINTY_COUNT", "Select exactly three uncertainty packages.", "uncertainty_packages"))
    uncertainty_rows: list[dict[str, Any]] = []
    uncertainty_ids: set[str] = set()
    contingency_min = Decimal("0")
    contingency_max = Decimal("0")
    for index, row in enumerate(uncertainty):
        path = f"uncertainty_packages[{index}]"
        if not isinstance(row, dict):
            errors.append(issue("UNCERTAINTY_OBJECT", "Each uncertainty package must be an object.", path)); continue
        wbs_id = row.get("wbs_id")
        if wbs_id in uncertainty_ids:
            errors.append(issue("UNCERTAINTY_DUPLICATE", f"Uncertainty package {wbs_id!r} is duplicated.", path)); continue
        uncertainty_ids.add(wbs_id)
        if wbs_id not in active_wbs:
            errors.append(issue("UNCERTAINTY_WBS", f"Unknown active WBS ID {wbs_id!r}.", f"{path}.wbs_id")); continue
        try:
            optimistic = dec(row.get("optimistic_hours"), f"{path}.optimistic_hours")
            likely = dec(row.get("most_likely_hours"), f"{path}.most_likely_hours")
            pessimistic = dec(row.get("pessimistic_hours"), f"{path}.pessimistic_hours")
        except ValueError as exc:
            errors.append(issue("UNCERTAINTY_HOURS", str(exc), path)); continue
        if not all(half_step(value) for value in (optimistic, likely, pessimistic)):
            errors.append(issue("UNCERTAINTY_STEP", "O, M, and P must be at least 1 and use 0.5-hour steps.", path))
        if not optimistic <= likely <= pessimistic:
            errors.append(issue("UNCERTAINTY_ORDER", "Uncertainty hours must satisfy O <= M <= P.", path))
        if wbs_id in estimate_hours and likely != estimate_hours[wbs_id]:
            errors.append(issue("UNCERTAINTY_MISMATCH", "Uncertainty M must equal the work package's base estimate.", path))
        expected_unrounded = (optimistic + Decimal("4") * likely + pessimistic) / Decimal("6")
        expected_rounded = round_up_half(expected_unrounded)
        contingency_min += expected_rounded - likely
        contingency_max += pessimistic - likely
        owner = active_wbs[wbs_id].get("owner")
        uncertainty_rows.append({
            "wbs_id": wbs_id, "optimistic_hours": decimal_text(optimistic),
            "most_likely_hours": decimal_text(likely), "pessimistic_hours": decimal_text(pessimistic),
            "expected_hours_unrounded": decimal_text(expected_unrounded),
            "expected_hours_rounded_up": decimal_text(expected_rounded),
            "expected_labor_value_unrounded": decimal_text(expected_rounded * RATES[owner]) if owner in RATES else None,
        })

    contingency = packet.get("contingency") if isinstance(packet.get("contingency"), dict) else {}
    try:
        contingency_hours = dec(contingency.get("hours"), "contingency.hours")
    except ValueError as exc:
        errors.append(issue("CONTINGENCY_HOURS", str(exc), "contingency.hours")); contingency_hours = Decimal("0")
    holder = contingency.get("holder")
    contingency_phase = contingency.get("phase_id")
    if holder not in RATES:
        errors.append(issue("CONTINGENCY_HOLDER", "Name one approved team member as contingency holder.", "contingency.holder"))
    if contingency_phase not in phase_by_id:
        errors.append(issue("CONTINGENCY_PHASE", "Assign contingency to one valid phase.", "contingency.phase_id"))
    if not str(contingency.get("justification", "")).strip():
        errors.append(issue("CONTINGENCY_REASON", "Explain the selected contingency.", "contingency.justification"))
    if len(uncertainty_rows) == 3 and not contingency_min <= contingency_hours <= contingency_max:
        errors.append(issue("CONTINGENCY_RANGE", "Selected contingency is outside the calculated range.", "contingency.hours"))
    if holder in RATES and contingency_phase in phase_by_id:
        hours_person_phase[(contingency_phase, holder)] += contingency_hours
        start, end = phase_dates[contingency_phase]
        if end <= VOTE_DATE:
            pre_hours += contingency_hours
        elif start >= POST_START:
            post_hours += contingency_hours

    capacity_rows: list[dict[str, Any]] = []
    for phase_id, (start, end) in phase_dates.items():
        for person in RATES:
            paper, source = paper_capacity(start, end, person)
            assigned = hours_person_phase[(phase_id, person)]
            realistic = realistic_lookup.get((phase_id, person))
            if assigned > paper:
                errors.append(issue("PAPER_CAPACITY", f"{person} exceeds paper capacity in {phase_id}.", f"capacity.{phase_id}.{person}"))
            if realistic is not None and realistic > paper:
                errors.append(issue("REALISTIC_ABOVE_PAPER", f"Realistic capacity for {person} cannot exceed paper capacity in {phase_id}.", f"realistic_capacity.{phase_id}.{person}"))
            if realistic is not None and assigned > realistic:
                flags.append(issue("REALISTIC_CAPACITY_PRESSURE", f"{person} exceeds student-declared realistic capacity in {phase_id}; revise or record a reason.", f"capacity.{phase_id}.{person}", hard=False))
            utilization = assigned / paper * 100 if paper else Decimal("0")
            capacity_rows.append({
                "phase_id": phase_id, "resource": person, "paper_hours": decimal_text(paper),
                "paper_capacity_source": source,
                "realistic_hours": decimal_text(realistic) if realistic is not None else None,
                "assigned_hours_including_contingency": decimal_text(assigned),
                "paper_utilization_percent": decimal_text(utilization),
                "paper_overallocated": assigned > paper,
                "realistic_overallocated": realistic is not None and assigned > realistic,
            })
    if pre_hours > PRE_VOTE_CEILING:
        errors.append(issue("PRE_VOTE_CEILING", "Pre-vote hours including contingency exceed 525.", "calculations.pre_vote_hours"))
    if post_hours > POST_VOTE_CEILING:
        errors.append(issue("POST_VOTE_CEILING", "Post-vote hours including contingency exceed 65.5.", "calculations.post_vote_hours"))

    deliverables = packet.get("project", {}).get("deliverables", []) if isinstance(packet.get("project"), dict) else []
    if isinstance(deliverables, list):
        represented = {row.get("deliverable_id") for row in active_wbs.values()}
        for deliverable in deliverables:
            deliverable_id = deliverable.get("deliverable_id") if isinstance(deliverable, dict) else deliverable
            if deliverable_id and deliverable_id not in represented:
                errors.append(issue("DELIVERABLE_WITHOUT_WORK", f"Approved deliverable {deliverable_id!r} has no active supporting work.", "project.deliverables"))

    final_explanation = packet.get("final_explanation")
    if not isinstance(final_explanation, str) or not final_explanation.strip():
        errors.append(issue("FINAL_EXPLANATION", "The student's final explanation is required for readiness.", "final_explanation"))

    accepted_flags = packet.get("accepted_flags", [])
    accepted_codes = {
        item.get("code") for item in accepted_flags
        if isinstance(item, dict) and str(item.get("reason", "")).strip()
    } if isinstance(accepted_flags, list) else set()
    unresolved_flags = [item for item in flags if item["code"] not in accepted_codes]

    labor_total = sum((dec(row["unrounded_labor_value"], "labor") for row in labor_lines), Decimal("0"))
    by_person_total = sum(totals_person.values(), Decimal("0"))
    by_phase_total = sum(totals_phase.values(), Decimal("0"))
    reconciles = labor_total == by_person_total == by_phase_total
    if not reconciles:
        errors.append(issue("RECONCILIATION", "Deterministic labor totals do not reconcile.", "calculations"))

    calculations = {
        "rate_table_version": RATE_TABLE_VERSION,
        "rate_table_approved": RATE_TABLE_APPROVED,
        "labor_lines": labor_lines,
        "labor_total_unrounded": decimal_text(labor_total),
        "labor_total_display_dollars": display_dollars(labor_total),
        "labor_by_person_unrounded": {key: decimal_text(value) for key, value in totals_person.items()},
        "labor_by_phase_unrounded": {key: decimal_text(value) for key, value in totals_phase.items()},
        "cash_lines": cash_lines,
        "cash_subtotal_unrounded": decimal_text(cash_total),
        "cash_contingency_unrounded": decimal_text(cash_contingency),
        "cash_total_unrounded": decimal_text(cash_total_with_contingency),
        "cash_total_display_dollars": display_dollars(cash_total_with_contingency),
        "cash_within_ceiling": cash_total_with_contingency <= CASH_CEILING,
        "uncertainty_packages": uncertainty_rows,
        "contingency_min_hours": decimal_text(contingency_min),
        "contingency_max_hours": decimal_text(contingency_max),
        "selected_contingency_hours": decimal_text(contingency_hours),
        "pre_vote_hours_including_contingency": decimal_text(pre_hours),
        "post_vote_hours_including_contingency": decimal_text(post_hours),
        "capacity": capacity_rows,
        "reconciles": reconciles,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": "v550-agent-2-resource-cost-advisor-student/cost_engine.py",
        "calculations": calculations,
        "readiness": {
            "ready": not errors and not unresolved_flags,
            "status": "YES" if not errors and not unresolved_flags else "NOT YET",
            "hard_blockers": errors,
            "advisory_flags": flags,
            "unresolved_advisory_flags": unresolved_flags,
            "accepted_flag_codes": sorted(accepted_codes),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        if not isinstance(packet, dict):
            raise ValueError("packet root must be a JSON object")
        result = evaluate(packet)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

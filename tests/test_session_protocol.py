from __future__ import annotations

import unittest

from support import load_script

protocol = load_script("session_protocol")


class SessionProtocolTests(unittest.TestCase):
    def test_consent_notice_is_first_and_contains_no_wbs_request(self):
        state, message = protocol.transition({}, "START")
        self.assertEqual(state["state"], "AWAITING_CONSENT")
        self.assertIn("confirm", message.casefold())
        self.assertNotIn("upload", message.casefold())

    def test_no_consent_means_no_wbs_request(self):
        state, _ = protocol.transition({}, "START")
        new_state, message = protocol.transition(state, "CONSENT_NO")
        self.assertEqual(new_state, state)
        self.assertNotIn("upload", message.casefold())

    def test_wbs_upload_requested_after_consent(self):
        state, _ = protocol.transition({}, "START")
        state, message = protocol.transition(state, "CONSENT_YES")
        self.assertEqual(state["state"], "AWAITING_WBS")
        self.assertIn("upload", message.casefold())

    def test_normalized_preview_requires_confirmation(self):
        state = {"state": "AWAITING_WBS"}
        state, message = protocol.transition(state, "WBS_NORMALIZED", [{"wbs_id": "WP-1"}])
        self.assertEqual(state["state"], "AWAITING_WBS_CONFIRMATION")
        self.assertIn("confirm", message.casefold())

    def test_guided_mode_is_default_and_asks_one_question(self):
        state, message = protocol.transition({"state": "AWAITING_WBS_CONFIRMATION"}, "WBS_CONFIRMED")
        self.assertEqual(state["mode"], "GUIDED")
        self.assertEqual(message.count("?"), 1)

    def test_independent_mode_returns_complete_packet(self):
        state, message = protocol.transition({"state": "DRAFTING", "mode": "GUIDED"}, "SELECT_INDEPENDENT")
        self.assertEqual(state["mode"], "INDEPENDENT")
        self.assertIn("Realistic capacity", message)
        self.assertIn("Uncertainty and contingency", message)

    def test_formal_review_requires_ready_signal(self):
        state, message = protocol.transition({"state": "DRAFTING"}, "FORMAL_REVIEW")
        self.assertEqual(state["state"], "DRAFTING")
        self.assertIn("has not run", message)
        state, _ = protocol.transition(state, "READY_FOR_REVIEW")
        self.assertEqual(state["state"], "FORMAL_REVIEW_REQUESTED")

    def test_protocol_never_requests_identity_salary_or_course_key(self):
        messages = [protocol.PRIVACY_NOTICE]
        state, _ = protocol.transition({}, "START")
        state, message = protocol.transition(state, "CONSENT_YES"); messages.append(message)
        rendered = " ".join(messages).casefold()
        for forbidden in ("student id", "your name", "course key", "salary amount"):
            self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()


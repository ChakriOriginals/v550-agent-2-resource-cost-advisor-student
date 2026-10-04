# V550 Agent 2 Resource and Cost Advisor Student

This local learning advisor helps you turn an approved Agent 1 WBS into a staffed, costed plan. You make the estimates and project decisions. Deterministic Python code applies the fixed course rates, calculates labor and cash totals, checks capacity, and reports readiness.

## Requirements

- Python 3.11 or newer
- Codex CLI or the Codex desktop app
- Your approved Agent 1 WBS as JSON, Markdown, a Living Project File, a review-bundle ZIP, or the standard Agent 1 DOCX table

No course account, API key, token, or environment file is required.

## Install

From this repository:

```bash
python3 tools/verify_package.py
python3 install.py
```

The installer copies the skill to `~/.agents/skills/v550-agent-2-resource-cost-advisor-student`. It stops instead of replacing an existing installation.

## Start

For Codex CLI, run `./start-v550.sh`. On macOS with the desktop app, run `./start-v550-desktop.sh`. Then invoke `$v550-agent-2-resource-cost-advisor-student`.

## What happens in a session

The advisor first explains the local privacy boundary and asks for your consent. Only after you agree does it ask you to upload the approved WBS. It verifies the file hash, reads the standard `WBS #`, `Work package`, `Assigned party`, `Hours`, and `Deadline` columns, and shows a normalized preview for your confirmation. It preserves the original IDs, hours, and deadlines. Parent links, deliverable links, full roster names, approved status, and pre-/post-vote labels may be derived only from the WBS numbering, fixed course roster, explicit Agent 1 approval statement, and fixed May 14 vote boundary; every derived field is disclosed.

Rows such as `1.0`, `2.0`, and `3.0` are treated as deliverable summaries, so their hours are checked against—but never added on top of—the detailed work-package hours. A schedule gap in an approved WBS is accepted at handoff and examined later during advising instead of causing the upload to be rejected.

Guided mode is the default and asks one focused question at a time. Independent mode gives you the complete blank packet so you can work at your own pace. Both modes use the same requirements:

`WBS -> phases -> realistic capacity -> estimates -> cash quantities -> three uncertainty ranges -> contingency -> calculation -> conflicts -> revision -> defense -> formal review`

There are no Agent 1 gates in this advisor. Formal review starts only when you clearly say that you are ready for review.

## Save and resume

Ask the advisor to save progress. It creates a versioned Markdown Living Project File under `V550 Agent 2 Work/`. In a later local chat, upload that file after accepting the same privacy notice.

## Generate the review bundle

After the advisor produces `## V550 Stage 2 Final Learning Review`, send `Generate my review bundle` as a new message. The advisor creates a read-only folder and ZIP under `V550 Agent 2 Review Bundles/`. The five-file bundle contains your structured work, Living Project File, final learning review, and complete visible student/advisor transcript. Local hashes detect changes but do not prove authorship.

## Troubleshooting

- If installation stops, move the old installed skill aside only after deciding you no longer need it, then rerun the installer.
- If the standard Agent 1 DOCX cannot be read, confirm that it contains an explicit Agent 1 approval statement and the `WBS #`, `Work package`, `Assigned party`, `Hours`, and `Deadline` columns. For other formats, include the original IDs and either explicit metadata or enough numbered deliverable rows and dates for deterministic normalization.
- If the advisor cannot find a local session for bundle generation, open this repository as the Codex workspace and retry in the same chat.
- Run `python3 -m unittest discover -s tests -p 'test_*.py'` for the full offline test suite.

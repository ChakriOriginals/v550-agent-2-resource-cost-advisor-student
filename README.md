# V550 Agent 2 Resource and Cost Advisor Student

This local learning advisor helps you turn an approved Agent 1 WBS into a staffed, costed plan. You make the estimates and project decisions. Deterministic Python code applies the fixed course rates, calculates labor and cash totals, checks capacity, and reports readiness.

## Requirements

- Python 3.11 or newer
- Codex CLI or the Codex desktop app
- Your approved Agent 1 WBS as JSON, Markdown, a Living Project File, a review-bundle ZIP, or a structured DOCX table

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

The advisor first explains the local privacy boundary and asks for your consent. Only after you agree does it ask you to upload the approved WBS. It verifies the file hash, preserves the WBS identifiers and links, shows a normalized preview, and waits for your confirmation.

Guided mode is the default and asks one focused question at a time. Independent mode gives you the complete blank packet so you can work at your own pace. Both modes use the same requirements:

`WBS -> phases -> realistic capacity -> estimates -> cash quantities -> three uncertainty ranges -> contingency -> calculation -> conflicts -> revision -> defense -> formal review`

There are no Agent 1 gates in this advisor. Formal review starts only when you clearly say that you are ready for review.

## Save and resume

Ask the advisor to save progress. It creates a versioned Markdown Living Project File under `V550 Agent 2 Work/`. In a later local chat, upload that file after accepting the same privacy notice.

## Generate the review bundle

After the advisor produces `## V550 Stage 2 Final Learning Review`, send `Generate my review bundle` as a new message. The advisor creates a read-only folder and ZIP under `V550 Agent 2 Review Bundles/`. The five-file bundle contains your structured work, Living Project File, final learning review, and complete visible student/advisor transcript. Local hashes detect changes but do not prove authorship.

## Troubleshooting

- If installation stops, move the old installed skill aside only after deciding you no longer need it, then rerun the installer.
- If a WBS cannot be read, export it as a structured JSON or Markdown table with the original IDs, parent links, deliverable links, scope status, and PRE_VOTE or POST_VOTE label.
- If the advisor cannot find a local session for bundle generation, open this repository as the Codex workspace and retry in the same chat.
- Run `python3 -m unittest discover -s tests -p 'test_*.py'` for the full offline test suite.


# Local Save Resume and Review Bundles

## Living Project File

Save a versioned Markdown checkpoint after formal review, when the student asks to save, and at session close. Include WBS filename and SHA-256; normalized WBS; phase map; paper and realistic capacity with reasons; ownership; estimates, methods, evidence, and fixed rate version; cash quantities and costs; three-point estimates; contingency; calculations; conflicts and resolutions; corrections; scope changes; overrides; assumptions; trade-offs; limitations; final explanation; readiness history; and revision history.

Every material revision records timestamp, affected item, previous value, new value, and the student's reason. To resume in a new chat, give the same privacy notice, then verify Living Project File schema version and source-WBS lineage before continuing.

## Two-turn closeout

First produce a visible message headed exactly `## V550 Stage 2 Final Learning Review`. Include completion state, workflow-component status, demonstrated learning, important revisions, unresolved required items, accepted flags and reasons, and one concrete next learning behavior. Use only visible work and deterministic results. Do not grade, infer motives, diagnose, or reveal hidden reasoning.

Then ask the student to send `Generate my review bundle` as a new message. On that next turn, run the local generator.

The new folder and ZIP under `V550 Agent 2 Review Bundles/` contain exactly:

1. `V550_AGENT2_REVIEW_SHEET.html`
2. `V550_AGENT2_REVIEW_RECORD.json`
3. `V550_AGENT2_LIVING_PROJECT_FILE.md`
4. `V550_AGENT2_REVIEW_MANIFEST.json`
5. `README.txt`

Never overwrite an existing bundle. Include visible user and assistant messages only; exclude system and developer instructions, hidden reasoning, tool calls, and tool output. Report validity only after `verify_review_bundle.py` returns `valid=true`. Local hashes detect changes but do not prove authorship.

Source workflow: `Resource and Cost Advisor Workflow.docx`, SHA-256 `0b484d5eed4b19537aecca9bac7b9248f88860ce1c4da5d1e0f73685eab62527`.


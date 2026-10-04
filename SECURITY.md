# Security and Privacy

This package runs locally. It has no remote course service, no telemetry, no GPT Actions, no faculty dashboard, no credential flow, and no automatic grading connection. The advisor does not need a student name, student ID, password, pseudonymous key, API credential, salary, or confidential employer information.

Codex keeps its normal local chat history. A review bundle contains the complete visible student/advisor conversation, the structured project record, and the final learning review. It excludes system and developer instructions, hidden reasoning, tool calls, and tool output.

Uploaded WBS files, local session state, Living Project Files, generated bundle folders, ZIP files, and common office-document formats are excluded by `.gitignore`. Always inspect `git status` before publishing a repository.

The generated bundle is marked read-only and checked with local SHA-256 hashes. These hashes can detect later changes, but without an instructor-held signing key they do not prove who authored the work.

If you discover a security issue, report the package version and a minimal fabricated example. Do not include student work, credentials, private course records, or confidential project data.


---
name: context-handoff
description: Preserve and continue long-running Codex conversations before their context window fills. Use when monitoring context usage, checkpointing at a threshold, creating a successor conversation, or validating a migration bundle. Do not use for ordinary short conversations.
metadata:
  short-description: Loss-aware context rollover for long Codex tasks
---

# Context Handoff

Protect long work with native compaction, durable checkpoints, and a verified successor.

## Thresholds

Read the latest session `token_count` event and calculate only `last_token_usage.input_tokens / model_context_window`. Never use cumulative token totals or rate-limit percentages.

- Below 75%: continue.
- At 75%: refresh a checkpoint after the current safe boundary.
- At 85%: create a clean successor after the turn, tool calls, and requested child waits finish.
- At 95%: stop optional expansion and prioritize migration.

Native compaction can reduce the ratio. Re-read the newest event immediately before rollover and cancel a stale rollover below 85%. Run `python3 scripts/context_handoff.py scan` for machine-readable usage.

Read [references/protocol.md](references/protocol.md) before migration and [references/schema.md](references/schema.md) when validating bundles.

## Checkpoint and takeover

Do not migrate mid-response, mid-write, during a tool call, or while a required approval or subagent wait is unresolved.

1. Prepare `handoff.md`: goal, acceptance, verified facts, inference, decisions, constraints, phase, active roles, write ownership, approvals/TODOs, Git state, evidence, risks, and exact next action.
2. Prepare `artifacts.json` with stable file, commit, task, approval, report, and link references; exclude secrets. Prepare `automations.json` with every task-bound automation's exact ID, name, kind, target task ID, status, schedule, prompt SHA-256, and notification policy; use an empty array only when there are no bindings.
3. Run `context_handoff.py build --automations <automations.json>`, passing the project root for saved projects, then run `verify`.
4. Create a clean task in the same saved project and proven working state, titled `原对话名｜续N`.
5. Require the successor to reload global/project instructions and return `MIGRATION_READY` with lineage and thread IDs, goal/phase hashes, pending approval/TODO IDs, active task IDs, write owner, Git HEAD/dirty paths, next action, and `operator_salutation: "妈妈"` unless explicitly overridden in the current conversation.
6. For every bound automation, reuse and rebind the existing automation to the exact successor task ID before takeover, authority switching, or predecessor archival. Only when a live view proves it is absent and creation remains within existing authorization may one minimal equivalent be created. Preserve schedule, prompt semantics/hash, notification policy, status, and scope; forbid duplicate ACTIVE same-duty automations.
7. Run `verify-migration` against fresh timestamped live automation evidence scoped to the exact predecessor target and all recorded IDs. A changed automation ID additionally requires a non-empty existing-authorization reference permitting one minimal equivalent. A bundle/configuration reference or update receipt is not proof. Applicable pin parity requires separate timestamped live `list_threads` evidence containing the exact successor ID; a Boolean cannot prove it. Missing or mismatched parity returns `MIGRATION_BLOCKED`, records `automation_rebind_failed`, and keeps the predecessor active and unarchived. Only after bundle, automation, and applicable pin parity pass may final `MIGRATION_READY` be emitted, the successor take authority, and the predecessor be archived—not deleted.

For Chief projects, reference all `.chief-of-staff` state files and preserve parents, phases, depth, peer edges, user actions, and cursors. If exact dirty-worktree continuity cannot be proven, keep the predecessor active and ask the user to choose the directory.

Use a per-lineage lock and migration number to prevent duplicates. Rebuild and re-check once after failure; on a second failure keep the predecessor active and create one explicit user-attention request.

If an already archived predecessor is discovered with a missing binding, repair the successor's automation without unarchiving or deleting the predecessor and without creating a duplicate task or same-duty automation.

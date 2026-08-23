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
2. Prepare `artifacts.json` with stable file, commit, task, approval, report, and link references; exclude secrets.
3. Run `context_handoff.py build`, passing the project root for saved projects, then run `verify`.
4. Create a clean task in the same saved project and proven working state, titled `原对话名｜续N`.
5. Require the successor to reload global/project instructions and return `MIGRATION_READY` with lineage and thread IDs, goal/phase hashes, pending approval/TODO IDs, active task IDs, write owner, Git HEAD/dirty paths, next action, and `operator_salutation: "妈妈"` unless explicitly overridden in the current conversation.
6. Compare every invariant. Only then inherit the pin state and archive—not delete—the predecessor.

For Chief projects, reference all `.chief-of-staff` state files and preserve parents, phases, depth, peer edges, user actions, and cursors. If exact dirty-worktree continuity cannot be proven, keep the predecessor active and ask the user to choose the directory.

Use a per-lineage lock and migration number to prevent duplicates. Rebuild and re-check once after failure; on a second failure keep the predecessor active and create one explicit user-attention request.


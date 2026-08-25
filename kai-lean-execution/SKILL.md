---
name: kai-lean-execution
description: Reduce avoidable token and context overhead while completing coding, diagnosis, review, or evidence-backed execution without weakening the user's goal, safety boundaries, or acceptance checks. Use only when explicitly invoked; do not use for context migration, complex project governance, or visual selection.
---

# KAI Lean Execution

Deliver the full requested outcome with the smallest sufficient investigation, coordination, and report.

## Lock the execution contract

Before acting, identify the original goal, available evidence, in-scope write surfaces, constraints, acceptance checks, and prohibited changes. Keep that contract stable. Token reduction never justifies narrowing the goal, omitting an explicit deliverable, or substituting a cheaper but materially different outcome.

## Use the lean execution loop

1. Reuse evidence already present in the conversation, repository, and verified tool results. Do not rediscover a settled fact unless it may be stale or conflicts with current evidence.
2. Search with `rg` or `rg --files` first. Read only directly relevant files and the smallest useful ranges. Expand scope only when a concrete dependency, conflict, or acceptance check requires it.
3. Prefer existing files, project capabilities, scripts, and tests over creating parallel mechanisms. Keep command output bounded to the evidence needed for the next decision.
4. Make one evidence-backed plan proportional to the task. Do not repeatedly restate the plan, investigation, or status unless something material changes.
5. Select the strongest safe in-scope continuation and execute it. Do not offer stopping, preserving a failed state, or delaying as peer choices while a safe authorized path remains. Escalate only when continuing itself needs a new permission or a new Chief.
6. Stop when the acceptance checks prove the requested outcome. Do not add speculative polish, unrelated refactors, or extra review rounds after completion.

## Keep coordination proportional

Use one agent for small, tightly coupled work and any task with one write surface. Delegate only when independent research, specialist separation, context isolation, or independent verification has a concrete benefit. Maintain exactly one writer for each shared file, external record, branch, deployment target, or deliverable. Do not inject subagents automatically merely because this Skill is active.

## Verify and report economically

Choose the minimum sufficient verification based on risk: one focused check for low-risk work, relevant tests plus an independent read-only check for medium-risk work, and stronger review only when the risk warrants it. Never skip safety, permission, correctness, or complete acceptance checks to save tokens.

Lead with the outcome. Cite compact evidence such as file paths, test summaries, commit hashes, or exact failing checks instead of pasting full logs. Distinguish verified facts from inference and open questions. Do not claim a fixed percentage of token savings or present an unverified result as complete.

## Boundaries

- Use `context-handoff` for real long-conversation checkpointing or migration; this Skill does not compress or transfer conversation history.
- Use `chief-of-staff` for complex project governance, durable roles, approval routing, or project-wide coordination.
- Follow the active visual-selection workflow for material visual choices; token economy never bypasses a preview or selection gate.
- Preserve all existing authorization boundaries. This Skill provides execution discipline, not permission for external writes, releases, destructive actions, payments, or production changes.

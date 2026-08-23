# Chief of Staff operating contract

This project is coordinated through one primary Codex task named `Chief of {{PROJECT_NAME}}`.

## Authority and communication

- The Chief of Staff owns decomposition, durable-task creation, task naming, dependency routing, status collection, conflict reconciliation, and the final user report.
- A task is the Chief of Staff only when its title matches the `primary_task_title` in `.chief-of-staff/project.json` or its initiating prompt explicitly assigns that role. Other tasks follow their delegated contract and return a structured handoff; they do not create a competing control plane.
- Ordinary questions stay inside the hierarchy. Escalate to the user only for required approvals, safety or security concerns, destructive or external actions, or product choices with materially different outcomes that evidence cannot resolve.
- Separate verified facts, inference, open questions, risks, and next steps in every report.

## Execution contract

Before delegation or implementation, record the goal, evidence, scope, non-scope, risk, acceptance checks, protected surfaces, dependencies, and prohibited changes.

- Use one agent for clear low-risk work with one write surface.
- For medium risk, use read-only scouting, one implementation writer, and read-only verification.
- For high risk, use read-only arbitration, one implementation writer, and independent read-only review.
- Use at most three active stages, two decision rounds, and one repair/re-check cycle.

## Write ownership

- A file, external record, branch, deployment target, or deliverable has at most one writer at a time.
- Scouts, reviewers, arbiters, and meeting participants are read-only unless the Chief of Staff explicitly transfers ownership.
- Preserve user changes and unrelated dirty-worktree changes. Never use destructive Git commands without explicit approval.
- Deletion, production changes, release, payment, external messages, and permission expansion require explicit user authorization immediately before the action.

## Durable tasks and meetings

- Name durable tasks `职务｜工作内容` and give each a complete execution contract.
- Durable tasks may summon temporary subagents for independent research, tests, or review when doing so materially improves speed or confidence.
- A temporary meeting must have a bounded question, participant roles, a synthesis owner, and a stopping condition.
- Let a task select an installed Skill when the request clearly matches its description; read the selected `SKILL.md` before acting.

## Handoff

Every delegated task ends with:

```markdown
## Handoff
- 已验证事实：
- 推断：
- 待确认项：
- 修改内容：
- 验收证据：
- 风险：
- 建议下一步：
```

Read-only tasks write `修改内容：无`. Writers list only their owned changes.

## Report approval gate

When `.chief-of-staff/project.json` sets `report_approval_required` to `true`, every milestone report and final handoff includes a stable `<task_id>:<report_sequence>` ID and requests `批准` or `退回修改`. The child opens a blocking review request so Codex marks it as needing attention; if the host cannot do that, it ends with `REVIEW_REQUIRED: <request_id>`. The Chief snapshots all active children after any wake-up, records every unseen request in `approval-queue.json`, and batches pending reports for the user in the Chief task. Only the user's explicit decision relayed by the Chief clears the gate.

## Persistent state

- `.chief-of-staff/project.json`: project identity and authorization boundary.
- `.chief-of-staff/task-registry.json`: durable task identifiers, ownership, dependencies, status, cursors, and result summaries.
- `.chief-of-staff/approval-queue.json`: deduplicated human-review requests and decisions.
- `.chief-of-staff/decisions.md`: append-only material decision log.
- `.chief-of-staff/status.md`: current consolidated report for the user.
- `.chief-of-staff/control-plane.json`: reserved adapter seam for a future external orchestrator.

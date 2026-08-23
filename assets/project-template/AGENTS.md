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

## Goal closure and active progression

- Before implementation, the Chief proposes and asks the user to confirm the final goal, deliverables, acceptance criteria, non-goals, and constraints. A new project permits only bounded read-only discovery before confirmation. In a migrated project, already-running non-high-impact tasks may finish, but no new task or phase starts before confirmation.
- A phase completion is not project completion. The project is complete only when the goal is confirmed and every final acceptance criterion has non-empty verification evidence in `project-plan.json`.
- Until completion, keep a phase task queued, running, or needing attention unless the project is explicitly waiting for the user or blocked with evidence and a release condition. If all phase tasks stop while final acceptance is unmet, immediately dispatch the next safe in-scope phase.
- Follow all active tasks with bounded waits. After any completion, failure, or attention event, snapshot every active task before deciding what comes next.
- A Chief report for an unfinished project always includes the final goal, current phase, verified progress, active roles, gap to delivery, and next checkpoint, even when no approval is pending.
- Management depth 1 is the Chief, depth 2 is a phase lead, and depth 3 is an execution role. Phase leads may create depth-3 tasks only when explicitly authorized in their contract. Temporary subagents cannot create durable roles. Depth 4 or deeper requires an approved `depth_expansion` request.
- The Chief is the sole writer of `project-plan.json`, `task-registry.json`, `approval-queue.json`, and consolidated status. Low-impact in-scope phases advance automatically; protected actions retain their separate approval requirements.

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
- `.chief-of-staff/project-plan.json`: confirmed final goal, acceptance evidence, project status, and phase plan.
- `.chief-of-staff/task-registry.json`: durable task identifiers, ownership, dependencies, status, cursors, and result summaries.
- `.chief-of-staff/approval-queue.json`: deduplicated human-review requests and decisions.
- `.chief-of-staff/decisions.md`: append-only material decision log.
- `.chief-of-staff/status.md`: current consolidated report for the user.
- `.chief-of-staff/control-plane.json`: reserved adapter seam for a future external orchestrator.

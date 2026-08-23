---
name: chief-of-staff
description: Initialize and coordinate a Codex project through one accountable Chief of Staff task. Use when the user asks to initialize Chief of Staff, 统筹项目, 组建团队, delegate durable work to named tasks, collect reports, or manage a complex project through one main conversation. Do not use for a small single-task request that does not need coordination.
metadata:
  short-description: One accountable task for coordinated project work
---

# Chief of Staff

Keep the user-facing conversation in one primary task while routing bounded work to durable Codex tasks or temporary subagents.

## Initialize a project

When the user says “初始化 Chief of Staff”, “启用 Chief of Staff”, or an equivalent explicit request:

1. Run `python3 scripts/init_project.py --target <project-root> --project-name <name>` from this skill directory. Never overwrite conflicts; report them.
2. Read `.chief-of-staff/project.json`. Its `primary_task_title` is `Chief of <project_name>`, for example `Chief of 个人web`.
3. If task-title tools are available, rename the current task to the exact `primary_task_title` value. Do not claim the rename succeeded unless the tool confirms it.
4. When `pin_primary_task` is `true`, resolve the current task ID and pin that task after the rename. Prefer a runtime-provided current task ID; otherwise list tasks and require one exact `primary_task_title` match in the current project context. Never pin an ambiguous match, and do not claim success unless the pin tool confirms it. If task pinning is unavailable, report that limitation while leaving project initialization intact.
5. Read the generated `AGENTS.md` and treat it with `project.json` as the project operating contract.
6. Read `.chief-of-staff/project-plan.json`. When `require_goal_confirmation` is `true` and `goal_status` is `unconfirmed`, infer a concise draft from available context and ask the user to confirm or revise the final goal, deliverables, acceptance criteria, non-goals, and constraints. Record a `goal_confirmation` request in `approval-queue.json`. A new project permits only bounded read-only discovery before confirmation. In a migrated project, already-running non-high-impact tasks may finish, but do not dispatch a new task or phase until the goal is confirmed.
7. After explicit confirmation, set `goal_status` to `confirmed` and `project_status` to `active`, record the confirmed values and time, define the first phase, and start at least one phase task. Record active durable tasks in `.chief-of-staff/task-registry.json`; record meaningful decisions in `.chief-of-staff/decisions.md`; maintain the consolidated user report in `.chief-of-staff/status.md`.

Initialization explicitly authorizes creation of project tasks needed to coordinate work in this project. It does not authorize publishing, deletion, production changes, payments, external messages, permission expansion, or other high-impact actions.

## Choose the smallest coordination layer

- Handle clear, low-risk work with one write surface in the Chief of Staff task.
- Create a durable Codex task when work needs its own long-lived context, role, status, or user-visible history. Title it `职务｜工作内容`.
- Use temporary subagents inside a task for bounded research, discussion, testing, or independent review. Temporary agents report to their parent task and do not become a second user-facing control plane.
- Do not create duplicate investigations or parallel writers for the same files, external record, branch, deployment target, or deliverable.
- An unconfirmed final goal permits only goal-clarifying read-only discovery, not implementation.

Read [references/coordination-protocol.md](references/coordination-protocol.md) before creating durable tasks or resolving conflicting reports. Read [references/state-schema.md](references/state-schema.md) before updating project state files programmatically.

## Delegate durable work

Use the Codex task tools available in the host. Resolve the Chief's current saved project and its `projectId` before creating a task. Create every durable child with that exact project target and verify the returned or listed child has the same `projectId`. Store it as `project_id` in the registry. For a Git repository, default a writing task to an isolated worktree; use a local checkout only when the user explicitly requests it or isolation is inappropriate and safe.

If the Chief has no saved project context, use temporary subagents by default. When separate durable history is genuinely required, ask the user to choose or save a project first; never silently create a projectless durable task. Codex may also show active project tasks in Recents because durable tasks are independently resumable peers. Keep queued, running, failed, and needs-attention children visible there for status and follow-up; do not pin them unless the user explicitly asks.

Every task prompt must include:

- role and why it is needed;
- goal and current evidence;
- scope and non-scope;
- owned write surface, or an explicit read-only constraint;
- deliverable and acceptance checks;
- dependencies and ordering;
- prohibited changes and approval boundaries;
- the structured handoff format from the coordination protocol.

Create tasks asynchronously, store returned task and host identifiers, then use bounded waits and compact status reads. Send follow-up instructions only to resolve a concrete omission, defect, or changed requirement. Limit a repair to one focused retry and one re-check.

When `report_approval_required` is `true`, include the report approval gate from the coordination protocol in every durable-task contract. A milestone report or final handoff remains unapproved until the user decides in the Chief task. After the first child becomes complete or needs attention, immediately snapshot every active child so simultaneous reports are collected rather than only the first wake-up.

For each new report, the Chief must:

1. Deduplicate it by `request_id` and append it to `.chief-of-staff/approval-queue.json` with `status: pending`.
2. Set the task registry status to `needs_attention` and preserve its latest cursor and report summary.
3. Present all pending reports to the user in one numbered approval batch in the Chief task, using the host's blocking user-input mechanism when available.
4. After the user chooses approve or request changes, update the queue, relay the decision to the child task, and only then move its registry status to `running` or `completed`.

Do not silently approve a report. If the child cannot open a native attention request, treat its `REVIEW_REQUIRED` handoff marker as the fallback signal and surface the approval request from the Chief task instead.
Report approval acknowledges the handoff only. It never authorizes deletion, release, production changes, payments, external messages, permission expansion, or another separately protected action.

When `archive_completed_child_tasks` is `true`, archive a durable child only after the user explicitly approves its final handoff, the Chief records its evidence and result in project state, and no retry or dependent follow-up remains. Then set its registry status to `archived` while preserving `task_id`, `host_id`, `project_id`, cursor, and result summary. Archiving is reversible; never archive a queued, running, failed, needs-attention, or changes-requested task.

## Maintain goal closure and active progress

Treat a phase completion as evidence, not project completion. The project is `completed` only when the final goal is confirmed and every acceptance criterion is `verified` with non-empty evidence in `project-plan.json`.

Until then, maintain at least one of these conditions:

- a phase task is `queued`, `running`, or `needs_attention`;
- `project_status` is `awaiting_user` with an exact decision request;
- `project_status` is `blocked` with verified evidence, attempted remedies, an owner, and a release condition.

If all phase tasks stop or complete while final acceptance remains unmet, immediately define and dispatch the next phase. `auto_advance_low_impact: true` authorizes this for safe in-scope work; it does not expand any protected approval boundary. Follow active tasks with bounded waits. After any task completes, fails, or needs attention, take one immediate snapshot of every active task, reconcile all results, update state, and either dispatch the next work or ask the user for the precise decision required.

Never answer only “当前无待审批事项” for an unfinished project. A concise Chief report must still include the confirmed final goal, current phase, verified progress, active roles, gap to final delivery, and next checkpoint.

## Enforce the management hierarchy

Use management depth `1` for the Chief, `2` for phase leads, and `3` for execution roles. A phase lead may create and manage depth-3 durable tasks when its contract explicitly grants that authority. Temporary subagents at depth 3 are bounded helpers, do not count as another durable management layer, and cannot create durable tasks.

Before creating depth 4 or deeper, add a `depth_expansion` request to the approval queue and ask the user. Include the proposed depth, phase, roles, reason, duration, and impact of refusing. Do not create the deeper task before explicit approval. The Chief remains the sole writer of `project-plan.json`, `task-registry.json`, `approval-queue.json`, and the consolidated status even when a phase lead creates child tasks.

## Use skills and temporary subagents

Let each task select an installed skill when its description clearly matches the delegated work. The task must read and follow that skill before acting. Do not force a skill merely because it is available.

Use temporary subagents only for independent lanes that improve speed, context isolation, or verification. A meeting has a named question, bounded participants, a required synthesis, and a stopping condition. The parent task waits for requested participants and returns one reconciled report.

## Consolidate for the user

Distinguish:

- **已验证事实**: supported by files, commands, tests, task results, or cited sources;
- **推断**: reasoned conclusions not directly verified;
- **待确认项**: decisions or missing information that cannot safely be inferred;
- **风险**: impact, likelihood, mitigation, and owner;
- **下一步**: owner, action, dependency, and acceptance condition.

Only escalate approvals, security or safety concerns, destructive or external actions, and product decisions that materially change the outcome. Keep ordinary coordination inside the project hierarchy.

# Project state schema

State lives in `.chief-of-staff/` and remains portable across future control planes.

## project.json

- `schema_version`: currently `1`.
- `project_name`: initialized project name.
- `primary_task_title`: generated as `Chief of <project_name>`, for example `Chief of 个人web`.
- `pin_primary_task`: boolean; when `true`, the Skill pins the main task after renaming it.
- `report_approval_required`: boolean; when `true`, milestone and final reports remain pending until the user decides through the Chief task.
- `require_goal_confirmation`: boolean; when `true`, implementation waits for explicit user confirmation of the final goal contract.
- `max_management_depth`: positive integer; defaults to `3` for Chief → phase lead → execution role.
- `auto_advance_low_impact`: boolean; permits the Chief to start the next safe in-scope phase without another approval.
- `proactive_follow_up`: boolean; requires bounded task waits, full active-task snapshots, and next-phase dispatch while final acceptance is unmet.
- `durable_child_scope`: `same_project`; every durable child must use the Chief's saved project ID.
- `archive_completed_child_tasks`: boolean; archive a child after approved final handoff and durable state capture.
- `projectless_child_policy`: `temporary_subagents`; a projectless Chief must not silently create projectless durable tasks.
- `control_plane`: `native` for the Codex-native implementation.
- `task_title_pattern`: durable task naming convention.
- `approval_required`: actions that always require explicit user authorization.

## project-plan.json

- `goal_status`: `unconfirmed` or `confirmed`.
- `project_status`: `awaiting_goal`, `active`, `awaiting_user`, `blocked`, or `completed`.
- `final_goal`, `deliverables`, `non_goals`, and `constraints`: the user-confirmed goal contract.
- Each acceptance criterion contains a unique `criterion_id`, `description`, `status` (`pending`, `verified`, or `failed`), and an evidence array.
- `confirmed_at` and `current_phase_id` are strings or `null`.
- Each phase contains a unique `phase_id`, title, objective, status, acceptance criteria, task IDs, and result summary.
- `completed` is valid only for a confirmed goal with at least one acceptance criterion and non-empty evidence on every verified criterion.

## task-registry.json

- `schema_version`: currently `1`.
- `tasks`: array of durable task records.
- Each task record requires `task_id`, `title`, `role`, `objective`, and `status` strings; `host_id`, `project_id`, `last_cursor`, `result_summary`, `parent_task_id`, and `phase_id` are strings or `null`; `management_depth` is a positive integer; `write_surface` and `depends_on` are arrays of strings.
- Unknown additional keys must be preserved so a future adapter can extend the format.

## approval-queue.json

- `schema_version`: currently `1`.
- `requests`: array of review requests owned and written only by the Chief.
- Each request requires a `request_kind`: `goal_confirmation`, `report_review`, or `depth_expansion`.
- Shared fields are `request_id`, `submitted_at`, `summary`, `requested_decision`, `status`, `decided_at`, and `decision_note`; task fields and `report_type` may be `null` for non-report requests.
- `report_type` is `progress` or `final` for `report_review` and `null` otherwise; `status` is `pending`, `approved`, `changes_requested`, or `superseded`.
- `request_id` is the deduplication key. Never insert a second record for the same ID; update the existing record after a decision.

Write updates atomically when scripting: write valid JSON to a sibling temporary file and replace the original. Do not erase an existing task or approval record merely because the corresponding task is unavailable in a single status query.

## control-plane.json

This is the adapter seam. `provider` is `codex-native`; `adapter` is `null` until an external control plane is explicitly installed. Future adapters must preserve `project.json`, `project-plan.json`, `task-registry.json`, and the approval rules.

## Markdown logs

- `decisions.md` is append-only for material decisions. Record date, decision, evidence, alternatives, owner, and consequences.
- `status.md` is the replaceable consolidated report shown to the user. Preserve the headings for final goal, current phase, facts, inference, open questions, pending reports, active roles, delivery gap, risks, next steps, and next checkpoint.

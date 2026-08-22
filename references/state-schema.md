# Project state schema

State lives in `.chief-of-staff/` and remains portable across future control planes.

## project.json

- `schema_version`: currently `1`.
- `project_name`: initialized project name.
- `primary_task_title`: generated as `Chief of <project_name>`, for example `Chief of 个人web`.
- `pin_primary_task`: boolean; when `true`, the Skill pins the main task after renaming it.
- `control_plane`: `native` for the Codex-native implementation.
- `task_title_pattern`: durable task naming convention.
- `approval_required`: actions that always require explicit user authorization.

## task-registry.json

- `schema_version`: currently `1`.
- `tasks`: array of durable task records.
- Each task record requires `task_id`, `title`, `role`, `objective`, and `status` strings; `host_id`, `last_cursor`, and `result_summary` are strings or `null`; `write_surface` and `depends_on` are arrays of strings.
- Unknown additional keys must be preserved so a future adapter can extend the format.

Write updates atomically when scripting: write valid JSON to a sibling temporary file and replace the original. Do not erase an existing task record merely because the corresponding task is unavailable in a single status query.

## control-plane.json

This is the adapter seam. `provider` is `codex-native`; `adapter` is `null` until an external control plane is explicitly installed. Future adapters must preserve `project.json`, `task-registry.json`, and the approval rules.

## Markdown logs

- `decisions.md` is append-only for material decisions. Record date, decision, evidence, alternatives, owner, and consequences.
- `status.md` is the replaceable consolidated report shown to the user. Preserve the headings for facts, inference, open questions, risks, and next steps.

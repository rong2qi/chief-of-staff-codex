# Project state schema

State lives in `.chief-of-staff/` and remains portable across future control planes.

## project.json

- `schema_version`: currently `1`.
- `project_name`: initialized project name.
- `primary_task_title`: generated as `Chief of <project_name>`, for example `Chief of 个人web`.
- `pin_primary_task`: `false` for an ordinary Chief. It may be `true` only for a mandatory core role, an operator-approved optional Chief, or a grandmothered optional Chief pending value review. The matching evidence lives in `pin-state.json`.
- `report_review_mode`: `all_reports` or `exception_only`. `exception_only` lets the Chief approve routine child handoffs while preserving operator gates for enumerated exceptions and final project completion.
- `report_approval_required`: backward-compatible boolean projection; `true` only for `all_reports`, `false` for `exception_only`.
- `governance_model`: `standard` or `chair_led_cabinet`.
- `operator_role`: `operator` or `chair`.
- `routine_administration_owner`: `project_chief` under `chair_led_cabinet`.
- `auditor_authority`: `evidence_only` under `chair_led_cabinet`.
- `direct_report_policy`: `standard` or `chain_of_command`.
- `partial_pause_policy`: `project` or `affected_surface_only`.
- `operator_escalation_policy`: `direct` or `statutory_exceptions_via_hubs`.
- `continuation_policy`: `standard` or `advance_best_safe_in_scope_path`, projected from validated optional governance preferences.
- `ordinary_failure_policy`: bounded repair behavior; the enabled continuation policy uses `continue_bounded_diagnosis_repair_and_verification`.
- `continuation_escalation_policy`: `existing_approval_boundaries` by default or `new_permission_or_new_chief` under the enabled continuation policy.
- `require_goal_confirmation`: boolean; when `true`, implementation waits for explicit user confirmation of the final goal contract.
- `project_classification_policy`: fixed `classify_after_goal_confirmation`.
- `deliverable_product_discovery_policy`: fixed `required_before_production`.
- `production_start_policy`: fixed `deny_until_product_discovery_passed_or_coordination_exempt`.
- `product_discovery_state_file`: fixed `.chief-of-staff/product-discovery.json`.
- `legacy_allowlist_digest`: `null` for a new project; a legacy migration stores the SHA-256 digest of its one-time phase/task allowlist so later allowlist expansion fails validation.
- `durable_goal_enabled`: boolean; enables durable goal tracking only after the final goal contract is confirmed.
- `execution_mode`: `effective_throughput`; bounded parallel delivery with evidence checkpoints.
- `max_parallel_phase_lanes`: positive integer; independent active phase lanes, default `2`.
- `no_evidence_checkpoint_limit`: positive integer; stop and self-check after this many evidence-free checkpoints, default `2`.
- `visual_selection_gate`: `disabled` by public default, or `operator_after_clickable_preview` when a validated optional profile enables the central preview gate.
- `visual_review_hub_title`: non-empty review-hub title; the public template uses `Chief of Creative Direction｜创意总监`, while a project preference may override it. The general Chief task and TODO are not visual hubs.
- `max_management_depth`: positive integer; defaults to `3` for Chief → phase lead → execution role.
- `auto_advance_low_impact`: boolean; permits the Chief to start the next safe in-scope phase without another approval.
- `proactive_follow_up`: boolean; requires bounded task waits, full active-task snapshots, and next-phase dispatch while final acceptance is unmet.
- `durable_child_scope`: `same_project`; every durable child must use the Chief's saved project ID.
- `archive_completed_child_tasks`: boolean; archive a child after approved final handoff and durable state capture.
- `projectless_child_policy`: `temporary_subagents`; a projectless Chief must not silently create projectless durable tasks.
- `peer_coordination_enabled`: boolean; permits bounded direct messages between registered same-project roles.
- `peer_contact_policy`: `registered_same_project`; only Chief-approved registry edges may communicate directly.
- `subagent_meetings_enabled`: boolean; permits durable roles to convene bounded temporary-agent meetings.
- `max_meeting_participants`: positive integer; maximum temporary participants per meeting, default `3`.
- `control_plane`: `native` for the Codex-native implementation.
- `task_title_pattern`: non-Chief durable-role naming convention. Durable Chiefs use `Chief of <domain or project>｜<optional local-language label>`; only the registered global general office and TODO may omit the prefix.
- `approval_required`: actions that always require explicit user authorization.

## pin-state.json

- `role_class`: `ordinary_chief`, `mandatory_core`, `approved_optional_chief`, or `grandmothered_optional_chief`.
- `authorization_status`: recommendation/approval state. Approved optional roles require both `recommendation_ref` and `operator_approval_ref`; grandmothered roles remain `grandmothered_pending_review` and cannot inherit a slot before approval.
- `pin_status`: `unpinned`, `pending_verification`, `verified`, `verification_failed`, `capacity_waiting`, `grandmothered_preserved`, or `superseded`. Ordinary Chiefs remain unpinned; full capacity is a waiting condition, not a defect.
- `verified_thread_id` and `verified_at`: exact-ID evidence from a fresh `list_threads` result. A pin-operation receipt is never sufficient.
- `successor_inheritance_eligible`: true only for a mandatory or approved optional lineage.
- `capacity_status` and `exclusion_reasons`: observed recommendation inputs without any automatic mutation.
- `successor`: bounded same-lineage handoff state. Takeover requires `MIGRATION_READY`, exact-list verification, and one safe replacement at most; predecessor archival requires verified takeover.

New projects start as ordinary and unpinned. An older managed project with `pin_primary_task=true` and no pin state migrates to an ID-free `grandmothered_optional_chief` record so its existing pin is preserved pending value review rather than silently removed.

Pre-matriarchal pin-state enum values are accepted only by the centralized input migration shim, rewritten once to the current grandmothered enum values, and never emitted again. The migration is idempotent and does not change slot eligibility, approval, capacity, or successor behavior.

## product-discovery.json

This mutable file is the single source of truth for project classification and the product-discovery gate. `project.json` contains only the fixed public policy.

- `classification_status`: `pending`, `classified`, or `legacy_unclassified`.
- `project_classification`: `unclassified`, `deliverable_project`, or `coordination_only`.
- `classification_reason`, `classified_at`, and `classification_evidence_refs`: decision basis and traceable evidence. A coordination exemption also requires non-empty `exemption_reason`.
- `product_manager_required`: `null` before classification, `true` for deliverable projects, and `false` for coordination-only projects.
- `gate_status`: `awaiting_classification`, `legacy_pending`, `awaiting_product_manager`, `in_progress`, `blocked`, `passed`, or `exempt`.
- `product_manager`: owner ID/kind, fixed management depth `2`, runtime mode, and any runtime limitation. The Product Manager is a phase lead, not a Chief or second control plane.
- `lanes`: exactly `project_initiation`, `requirements_analysis`, `market_research`, and `architecture_feasibility`. Each lane records status, execution mode, owner, depth, immutable `delegation_allowed: false`, artifact refs, and evidence refs.
- `required_deliverables`: the project charter; market/competitor research; user research/personas; business/policy feasibility; requirements inventory/prioritization; advisory architecture feasibility; and risk/evidence-gap/MVP recommendation. Every item records status plus artifact and evidence refs.
- `synthesis_coverage`: fixed boolean coverage for problem definition; goals/non-goals/metrics; market/competitors; users/pain points/personas; policy/business feasibility; multi-source requirements and tiering; false/duplicate/high-difficulty rejection evidence; advisory architecture; risks/gaps/MVP; and the evidence index. A passed gate requires every value to be `true`.
- `evidence_index`: uniquely identified `verified_fact`, `assumption`, or `open_question` entries. Every verified fact requires a traceable source, verification method, and verification time. Assumptions and open questions remain explicitly unverified evidence-gap records. Lane and deliverable evidence refs must resolve to evidence-index IDs, and a passed gate requires at least one verified-fact reference for every lane and deliverable; artifact refs must be traceable, and local `repo://` refs must resolve inside the project root.
- `gate_decision`: proceed/conditional/no-go decision, conditions, material-direction state, review route/status, and decision reference. `passed` requires complete evidence and an approved review; unresolved `operator_required` cannot pass.
- `guardrails`: fixed `advisory_non_binding` architecture output, `creative_director_only` visual direction, and `separate_explicit_approval` for protected actions.
- `legacy_allowlist`: migration-time phase/task IDs that alone may use `legacy_existing`. It is an audit snapshot, not a label that new work may claim.
- `migration_note`: `null` for new projects or a non-private legacy migration explanation.

## project-plan.json

- `goal_status`: `unconfirmed` or `confirmed`.
- `project_status`: `awaiting_goal`, `active`, `awaiting_user`, `blocked`, or `completed`.
- `final_goal`, `deliverables`, `non_goals`, and `constraints`: the user-confirmed goal contract.
- Each acceptance criterion contains a unique `criterion_id`, `description`, `status` (`pending`, `verified`, or `failed`), and an evidence array.
- `confirmed_at` and `current_phase_id` are strings or `null`.
- Each phase contains a unique `phase_id`, title, objective, status, `phase_class`, acceptance criteria, task IDs, and result summary. `phase_class` is `goal_discovery`, `product_discovery`, `production`, `coordination`, or migration-allowlisted `legacy_existing`.
- `completed` is valid only for a confirmed goal with at least one acceptance criterion and non-empty evidence on every verified criterion.

## task-registry.json

- `schema_version`: currently `1`.
- `tasks`: array of durable task records.
- Each task record requires `task_id`, `title`, `role`, `objective`, `status`, and `work_class` strings; `host_id`, `project_id`, `last_cursor`, `result_summary`, `parent_task_id`, and `phase_id` are strings or `null`; `management_depth` is a positive integer; `write_surface`, `depends_on`, and `coordination_with` are arrays of task-ID strings. `work_class` is `goal_discovery`, `product_discovery`, `production_execution`, `coordination_only`, or migration-allowlisted `legacy_existing`.
- Unknown additional keys must be preserved so a future adapter can extend the format.

## approval-queue.json

- `schema_version`: currently `1`.
- `requests`: array of review requests owned and written only by the Chief.
- Each request requires a `request_kind`: `goal_confirmation`, `report_review`, or `depth_expansion`.
- Shared fields are `request_id`, `submitted_at`, `summary`, `requested_decision`, `status`, `decided_at`, and `decision_note`; task fields and `report_type` may be `null` for non-report requests.
- `report_type` is `progress` or `final` for `report_review` and `null` otherwise; `status` is `pending`, `approved`, `changes_requested`, or `superseded`.
- `request_id` is the deduplication key. Never insert a second record for the same ID; update the existing record after a decision.
- A `report_review` may include `review_route` (`chief` or `operator`), `reviewer`, `reviewed_at`, `decision_basis`, `evidence_refs`, and `human_gate_reason`. Under `exception_only`, a Chief-approved routine report is stored directly as `approved`; only an enumerated exception remains `pending` for the operator.

Write updates atomically when scripting: write valid JSON to a sibling temporary file and replace the original. Do not erase an existing task or approval record merely because the corresponding task is unavailable in a single status query.

## control-plane.json

This is the adapter seam. `provider` is `codex-native`; `adapter` is `null` until an external control plane is explicitly installed. Future adapters must preserve `project.json`, `project-plan.json`, `task-registry.json`, and the approval rules.

## Markdown logs

- `decisions.md` is append-only for material decisions. Record date, decision, evidence, alternatives, owner, and consequences.
- `status.md` is the replaceable consolidated report shown to the user. Validation requires the headings for final goal, current phase, product classification/gate, facts, inference, open questions, pending reports, active roles, delivery gap, risks, next steps, and next checkpoint. Legacy initialization inserts the missing product-gate heading without overwriting other status content.

## throughput.json

- `execution_mode`: `effective_throughput`.
- `max_parallel_phase_lanes` and `no_evidence_checkpoint_limit`: copied from the project policy at initialization and retained as operational state.
- `consecutive_no_evidence_checkpoints`: non-negative integer; increment only for a completed checkpoint without concrete acceptance evidence.
- `active_phase_lanes`: phase IDs currently consuming lane capacity.
- `last_evidence_checkpoint`: ISO-8601 timestamp or `null`.

## deployment-registry.json

- `deployments`: independent, append-preserving records with a unique `deployment_id`, `provider`, `environment`, `target`, `status`, evidence strings, and `production_approval_id`.
- Registration is inventory and evidence, not authorization. A production action requires a separate immediately-prior explicit user approval even if its registry entry has an approval ID.

## Optional preferences.json

- A project-scoped profile may live at `.chief-of-staff/preferences.json`; global profiles are stored at the absolute location selected during onboarding and referenced by the managed personal `AGENTS.md` block.
- Public project initialization does not create a profile unless `--preferences` is supplied. Missing or invalid optional preferences do not silently enable personal behavior.
- `automation_inheritance` is an anonymous disabled public contract for task-bound automation migration. It fixes the eight bundle fields, three pre-takeover rebind boundaries, reuse/missing-equivalent policy, preservation set, duplicate prohibition, live-evidence rules, joint bundle/automation/applicable-pin parity gate, `MIGRATION_BLOCKED`/`automation_rebind_failed` failure state, predecessor retention, and non-destructive historical repair.
- The top-level `report_review_mode` selects `exception_only` or `all_reports`. Optional sections cover `governance_model` (including its nested `continuation_policy`), `visual_selection_gate`, `american_english_coaching`, `audio_playback`, `operator_salutation`, `paused_title_prefix`, and `reminders`; only an explicit `enabled: true` activates a section.
- `audio_playback.storage_root` is absolute. An unavailable path produces text only and must never fall back to a different disk.

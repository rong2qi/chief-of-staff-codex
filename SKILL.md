---
name: chief-of-staff
description: Initialize and coordinate a Codex project through one accountable Chief of Staff task. Use when the user asks to initialize Chief of Staff, 统筹项目, 组建团队, delegate durable work to named tasks, collect reports, track unanswered Chief requests, configure reminders, or manage a complex project through one main conversation. Do not use for a small single-task request that does not need coordination.
metadata:
  short-description: One accountable task for coordinated project work
---

# Chief of Staff

## 新增执行政策 / New execution policy

- 默认 `effective_throughput`：最多两个独立阶段并行，每个检查点必须产生可验证证据；连续两个检查点无证据即停止并自查。
- `/goal` 仅用于已确认、可验收且没有人工审批门的目标。`durable_goal_enabled` 不会绕过目标确认或高影响操作审批。
- 默认汇报审查采用 `exception_only`：Chief 自行验收普通岗位进度与交接，只把目标确认、实质产品选择、视觉选择、高影响操作、安全问题、范围/所有权冲突、失败或证据不足、扩层和项目最终交付升级给操作者。
- 创意总监只在北京时间每天 11:00 和 20:00 执行有证据的主动扫描；最多保留一条待定创意建议。它同时是启用视觉确认门时唯一面向操作者的视觉审阅中心：可接收项目 Chief 的预览包、维护视觉待决队列，并在操作者决定后把原话回传来源 Chief。除这种有登记来源的视觉决定回传外，它只读其他项目、不主动干预、不修改项目文件。
- 云部署统一登记在独立 registry；登记不授权生产操作，生产变更、发布或回滚仍须紧邻操作前的明确用户批准。
- 视觉确认、暂停标题、操作者称呼和美式英语教学是可选个人策略；仅在已验证偏好档案中对应 `enabled` 为 `true` 时执行。
- 当 `governance_model.mode` 为 `chair_led_cabinet` 时，操作者是主席而不是日常审批员：项目 Chief 独立承担行政执行与普通验收；审计者只有证据核验权；“一人之下”只汇总非视觉法定例外；创意总监是唯一视觉审议入口；TODO 只提醒这两个权威入口。
- 当 `governance_model.continuation_policy.enabled` 为 `true` 时，项目 Chief 必须选择并执行证据最强、在范围内且安全的继续路径，不得在仍有安全推进方案时把停止、保留失败状态或延期作为并列选项交给操作者。只有继续本身需要新增权限或创建新 Chief 时才报备；普通失败仍由 Chief 通过限界诊断、修复或复检继续负责。

- Default `effective_throughput` permits at most two independent phase lanes. Every checkpoint needs verifiable evidence; stop and self-check after two evidence-free checkpoints.
- Use `/goal` only for a confirmed, testable goal with no human gate. `durable_goal_enabled` never bypasses confirmation or protected-action approval.
- Report review defaults to `exception_only`: the Chief reviews routine role progress and handoffs, escalating only goal confirmation, material product choices, visual choices, protected actions, safety issues, scope or ownership conflicts, failed or unverifiable work, depth expansion, and final project completion.
- The Creative Director runs evidence-backed proactive scans at 11:00 and 20:00 Beijing time and retains at most one pending creative recommendation. When the visual gate is enabled, it is also the only operator-facing visual review hub: it receives preview packets, owns the visual decision queue, and relays the operator's exact decision back to the source Chief. Outside that registered relay, it remains read-only and does not interfere with project work.
- Cloud deployments are recorded in an independent registry. Registration never authorizes a production operation, release, or rollback.
- Visual confirmation, pause-title decoration, operator salutation, and American-English coaching are optional personal policies. Apply them only when their validated profile sections are enabled.
- With `governance_model.mode = chair_led_cabinet`, the operator acts as chair rather than routine approver: project Chiefs own administration and ordinary acceptance, auditors have evidence-only authority, the general office consolidates non-visual statutory exceptions, the Creative Director is the sole visual review hub, and TODO reminds only those two authoritative channels.
- With `governance_model.continuation_policy.enabled`, each project Chief selects and executes the strongest evidence-backed safe in-scope continuation. It does not offer stopping, preserving a failed state, or delaying as peer options while a safe continuation exists. It escalates only when continuing itself requires a new permission or a new Chief; ordinary failures remain Chief-owned through bounded diagnosis, repair, and verification.

Keep the user-facing conversation in one primary task while routing bounded work to durable Codex tasks or temporary subagents.

## Apply chair-led cabinet governance

When validated preferences enable `governance_model` with mode `chair_led_cabinet`, apply [references/chair-led-governance.md](references/chair-led-governance.md) as the authority map.

- The operator holds only the reserved powers recorded in the profile: final-goal confirmation, material product direction, final visual selection, protected actions, Chief appointment/pause/removal, and final project acceptance or termination.
- Each project Chief is accountable for routine administration, task creation, evidence review, one bounded repair cycle, phase advancement, and child-task archival. A Chief must not convert work it can decide into an operator gate.
- Durable roles report through their registered parent. They do not address the operator directly for routine work. Emergency bypass is limited to evidence that the Chief is violating safety, concealing a high-impact risk, or is itself party to an unresolved ownership conflict.
- Auditors and verifiers report facts, PASS/FAIL/evidence-insufficient, and risk. They cannot approve product direction, widen scope, open an operator gate for ordinary test results, or order implementation.
- Non-visual statutory exceptions are sent as `CHAIR_BRIEF_READY` to the configured general-office task. Only that task may emit the operator-facing `USER_ACTION_REQUIRED` after deduplication and compression. Visual decisions go only to the configured Creative Director. Project Chiefs retain the source evidence but do not duplicate the request to the operator or TODO.
- Waiting for a decision pauses only the affected write surface. The Chief continues every safe lane that does not depend on that decision. Set the entire project to `awaiting_user` only when no independent safe lane remains.
- When the projected `continuation_policy` is `advance_best_safe_in_scope_path`, the Chief chooses that path autonomously and records its evidence. The policy never authorizes a protected action, bypasses a visual gate, hides safety/security evidence, or expands the confirmed goal.
- The operator brief contains only: the exact decision, why chair authority is required, material alternatives, the Chief's evidence-backed recommendation, the impact of delay, and one directly usable reply. Logs and full handoffs remain linked evidence.

## Configure optional operator preferences

Cloning or installing this Skill never runs setup. Enter onboarding only when the operator explicitly asks to configure or reconfigure Chief of Staff, or asks to initialize a project and no saved preference profile can be found. Read [references/operator-preferences.md](references/operator-preferences.md) before onboarding, profile validation, global-rule installation, or audio rendering.

When the host exposes a blocking selection UI, present the preset, salutation, and data-placement questions together. Put concise audience guidance directly in the preset descriptions: recommend full Chief coordination to enterprises and mature teams that need ownership, approval, and evidence trails; recommend the low-overhead `core` path to beginners and individuals, with one phase, one writer, lower-cost routing, and the optional audited explicit-only `$lean-code-path` companion derived from Ponytail when it is separately installed. Include the names `Ponytail` and `lean-code-path` in the help text so the recommendation is searchable. Never install or enable that companion Skill from onboarding without a separate explicit decision. Otherwise ask the same short questions conversationally. Show the resolved policies, destination, voice delivery, and fallback behavior, then require one Apply / Revise / Cancel decision. Cancel writes nothing. Do not repeat onboarding after a profile is saved.

Use `scripts/configure_preferences.py` for deterministic writes. Public defaults are neutral: no visual selection gate, coaching, audio, salutation, pause prefix, or reminders. The anonymous `operator-controlled-bilingual` preset enables operator-controlled visual selection, written/spoken/idiom coaching including casual chat, host-provided built-in voice delivery when available, and the pause prefix; salutation and reminder activation remain explicit choices. Offline written/spoken attachments remain an opt-in custom choice.

A global profile is referenced by the managed block in the personal `AGENTS.md`. A project profile lives at `.chief-of-staff/preferences.json` and overrides optional policies only for that project. Never publish a live profile or generated audio.

## Initialize a project

When the user says “初始化 Chief of Staff”, “启用 Chief of Staff”, or an equivalent explicit request:

1. Resolve optional preferences first. If onboarding is required, complete it before initialization. Run `python3 scripts/init_project.py --target <project-root> --project-name <name>` from this skill directory. For a project-scoped profile pass `--preferences <profile-path>`; for an active global profile pass `--policy-profile <profile-path>` so enabled governance and visual routing are projected into `project.json` without copying the private global profile into the project. Never overwrite conflicts; report them.
2. Read `.chief-of-staff/project.json`. Its `primary_task_title` is `Chief of <project_name>`, for example `Chief of 个人web`.
3. If task-title tools are available, rename the current task to the exact `primary_task_title` value. Do not claim the rename succeeded unless the tool confirms it.
4. `pin_primary_task` defaults to `true` for every newly initialized Chief. Resolve the current task ID and pin that task after the rename; the operator may unpin it manually later. Prefer a runtime-provided current task ID; otherwise list tasks and require one exact `primary_task_title` match in the current project context. Never pin an ambiguous match. A successful pin-tool response is not sufficient evidence: immediately list tasks and require the exact task ID to appear in `pinnedThreads` before reporting success. If pinning is unavailable or the independent list check fails, report the Chief as `pin_verification_failed` while leaving project initialization intact. Do not create a duplicate Chief while the original is active. At the next safe handoff boundary after its current authorized work is complete, archive the original with reason `unable_to_pin`, create exactly one replacement Chief in the same saved project, transfer the current goal/phase/approval/TODO/write-ownership handoff, and verify the replacement in `pinnedThreads` before calling it pinned. Never delete the original; do not use this fallback to change project scope or bypass approval gates.
5. Read the generated `AGENTS.md` and treat it with `project.json` as the project operating contract.
6. Read `.chief-of-staff/project-plan.json`. When `require_goal_confirmation` is `true` and `goal_status` is `unconfirmed`, infer a concise draft from available context and ask the user to confirm or revise the final goal, deliverables, acceptance criteria, non-goals, and constraints. Record a `goal_confirmation` request in `approval-queue.json`. A new project permits only bounded read-only discovery before confirmation. In a migrated project, already-running non-high-impact tasks may finish, but do not dispatch a new task or phase until the goal is confirmed.
7. After explicit confirmation, set `goal_status` to `confirmed` and `project_status` to `active`, record the confirmed values and time, define the first phase, and start at least one phase task. Record active durable tasks in `.chief-of-staff/task-registry.json`; record meaningful decisions in `.chief-of-staff/decisions.md`; maintain the consolidated user report in `.chief-of-staff/status.md`.

## Reflect explicit pause state in the Chief title

When `paused_title_prefix.enabled` is true and the operator explicitly pauses a project, use the thread-title tool to prefix its Chief with the configured value as soon as the pause decision is recorded. Preserve the saved project, thread ID, and pin state, and make the operation idempotent. On an explicit resume, remove exactly one leading configured prefix before restarting work. Do not infer a pause from an idle task, `awaiting_user`, `blocked`, a report gate, or an empty active-role list. When the preference is disabled, record pause state without decorating the title.

Initialization explicitly authorizes creation of project tasks needed to coordinate work in this project. It does not authorize publishing, deletion, production changes, payments, external messages, permission expansion, or other high-impact actions.

## Choose the smallest coordination layer

- Handle clear, low-risk work with one write surface in the Chief of Staff task.
- Create a durable Codex task when work needs its own long-lived context, role, status, or user-visible history. Title it `职务｜工作内容`.
- Use temporary subagents inside a task for bounded research, discussion, testing, or independent review. Temporary agents report to their parent task and do not become a second user-facing control plane.
- Do not create duplicate investigations or parallel writers for the same files, external record, branch, deployment target, or deliverable.
- An unconfirmed final goal permits only goal-clarifying read-only discovery, not implementation.

Read [references/coordination-protocol.md](references/coordination-protocol.md) before creating durable tasks or resolving conflicting reports. Read [references/state-schema.md](references/state-schema.md) before updating project state files programmatically.

When `visual_selection_gate.enabled` is true, read [references/visual-selection-governance.md](references/visual-selection-governance.md) before preparing options, changing visual state, or relaying a decision. When it is false, ordinary product-decision and approval boundaries still apply, but this specialized central preview gate does not.

The configured visual hub must be the single pinned `Chief of Creative Direction｜创意总监` task, not the general Chief-of-Staff conversation, a project Chief, a child role, or the TODO task. Project Chiefs and roles submit preview packets only to that hub and must not duplicate the same visual request to the operator elsewhere. The TODO scanner surfaces unresolved visual decisions only from the Creative Director task; it ignores copies in source project tasks. The general Chief task does not receive, store, approve, or relay visual packets.

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
- allowed peer task IDs from the registry and the purpose of each coordination edge;
- permission to convene bounded temporary-subagent meetings when enabled;
- the structured handoff format from the coordination protocol.

Create tasks asynchronously, store returned task and host identifiers, then use bounded waits and compact status reads. Send follow-up instructions only to resolve a concrete omission, defect, or changed requirement. Limit a repair to one focused retry and one re-check.

Read `report_review_mode` from `project.json`. `report_approval_required` remains a compatibility projection: `true` only for `all_reports`, `false` for `exception_only`.

In `all_reports`, every milestone report and final handoff remains unapproved until the user decides in the Chief task. In `exception_only`, the child submits `CHIEF_REVIEW_READY: <request_id>` rather than opening a human gate for routine work. The Chief checks scope, owned write surface, acceptance evidence, tests, protected-action boundaries, conflicts, and final-goal impact; it then records an evidence-backed Chief approval or requests changes. Visual option decisions still go through the Creative Director hub. After the first child becomes complete or needs attention, immediately snapshot every active child so simultaneous reports are collected rather than only the first wake-up.

Under enabled `chair_led_cabinet` governance, an operator-routed non-visual exception does not go directly from the project Chief to the operator. The Chief sends one `CHAIR_BRIEF_READY: <request_id>` packet to the configured general office. The general office verifies the exception category, deduplicates it, compresses it, and alone emits `USER_ACTION_REQUIRED`. The visual route remains exclusively with the Creative Director. Emergency bypass follows the narrow conditions in the governance reference.

For each new report, the Chief must:

1. Deduplicate it by `request_id` and append it to `.chief-of-staff/approval-queue.json` with its review route (`chief` or `operator`) and evidence summary.
2. Preserve the latest cursor and report summary. Use `needs_attention` only for an actual unresolved defect, conflict, missing evidence, or operator gate; routine Chief review may remain `running` until resolved.
3. Under `exception_only`, auto-review routine reports. Escalate to the operator only when at least one exact exception category applies, and record that category and evidence. Under `all_reports`, batch every pending milestone/final report for the operator.
4. Relay the resulting Chief or operator decision to the child, update the queue, and move the registry status to `running`, `completed`, or `needs_attention` as evidence requires.

Chief auto-approval is not silent: record reviewer `chief`, review time, checked acceptance evidence, decision basis, and the absence of exception conditions. If any required evidence is missing, request changes or escalate; never infer success. For an operator-routed exception, use `USER_ACTION_REQUIRED` or the host's attention mechanism. `REVIEW_REQUIRED` remains the legacy fallback for `all_reports`.
Report approval acknowledges the handoff only. It never authorizes deletion, release, production changes, payments, external messages, permission expansion, or another separately protected action.

When `archive_completed_child_tasks` is `true`, archive a durable child only after its final handoff is approved by the configured route, the Chief records its evidence and result in project state, and no retry or dependent follow-up remains. Under `exception_only`, a documented Chief review is sufficient for routine child completion; project final completion still requires the operator. Then set its registry status to `archived` while preserving `task_id`, `host_id`, `project_id`, cursor, and result summary. Archiving is reversible; never archive a queued, running, failed, needs-attention, or changes-requested task.

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

When `peer_coordination_enabled` is true, the Chief may add symmetric `coordination_with` edges between durable tasks whose verified `project_id` values match. Those tasks may message each other directly for a bounded dependency, interface, evidence request, or handoff. The sender includes the purpose, evidence, response needed, and deadline or stopping condition. The resulting decision or unresolved conflict is copied back to the Chief; routine peer sync does not open a human approval gate. The cross-project visual route is a narrow global exception: any project Chief may send a visual preview packet to the configured Creative Director hub, and that hub may return only the operator's exact decision and boundary to the source Chief. This exception never transfers write ownership or allows unsolicited project direction.

Peer dialogue never transfers write ownership, broadens scope, approves reports, or authorizes protected actions. The Chief must decide any ownership or scope change before implementation. If direct thread messaging is unavailable in a task runtime, the task sends the same structured coordination request through the Chief as a relay.

When `subagent_meetings_enabled` is true, any durable task may summon up to `max_meeting_participants` temporary subagents using the runtime's collaboration tools. Give each participant a distinct read-only lane by default, the meeting question, evidence, deliverable, and stopping condition. Temporary participants cannot create durable roles or delegate another management layer. The parent waits for every requested participant, resolves disagreement by evidence rather than majority vote, and sends one synthesis to its registered peers and the Chief. If the runtime lacks subagents, complete the work with the parent task and report the safe downgrade.

## Optional unanswered-Chief reminders

Unanswered-Chief reminders are one personal, cross-project service rather than one automation per project. Configure them only when the user asks to enable, disable, or change reminders and the preference profile allows them. Read [references/reminder-policy.md](references/reminder-policy.md), then maintain the personal policy file, one pinned TODO thread, and the minimum non-duplicated set of thread heartbeat automations. Saving `reminders.enabled: true` does not itself authorize creating an automation; follow the normal reminder workflow.

When disabled, pause every automation recorded by the policy so no scheduled run or notification occurs. When enabled, compile the user's timezone, inclusive daytime window, interval, and additional times into the exact schedule. Each run rebuilds a full snapshot and includes only unresolved explicit requests for approval, confirmation, decision, information, safety, or permissions. Under `exception_only`, routine child report reviews are excluded even if an older child emitted `REVIEW_REQUIRED`; include them only after the project Chief classifies an exact exception and emits `USER_ACTION_REQUIRED`. New Chief requests that require a reply end with `USER_ACTION_REQUIRED: <request_id>`; after a resolving user reply, the Chief records `USER_ACTION_RESOLVED: <request_id>`. The scanner still recognizes older unmarked non-report requests. A user opening or reading a Chief does not clear an item; a later user reply that resolves, supersedes, or rejects the request does. For visual selections, the scanner recognizes only the configured Creative Director task as authoritative and excludes visual copies in project Chiefs, roles, the general Chief task, and prior hubs. The TODO task is read-only and never replies to a Chief or approves anything.

## Preserve long-running context

When the personal `context-handoff` Skill is installed, apply its 75% checkpoint, 85% rollover, and 95% emergency policy to the Chief and every durable role. A Chief bundle references all `.chief-of-staff` state and preserves goals, phases, evidence, task parents/depths, peer edges, cursors, approvals, unanswered actions, write ownership, and the next checkpoint.

Require `MIGRATION_READY`. Migration cannot approve reports, change ownership, detach children, or complete acceptance. Only after parity may the successor inherit the pin and the predecessor be archived. If dirty-worktree continuity is not proven, keep the predecessor active and ask the user.

## Consolidate for the user

Distinguish:

- **已验证事实**: supported by files, commands, tests, task results, or cited sources;
- **推断**: reasoned conclusions not directly verified;
- **待确认项**: decisions or missing information that cannot safely be inferred;
- **风险**: impact, likelihood, mitigation, and owner;
- **下一步**: owner, action, dependency, and acceptance condition.

Only escalate approvals, security or safety concerns, destructive or external actions, and product decisions that materially change the outcome. Keep ordinary coordination inside the project hierarchy.

## Add optional American-English coaching

Only when `american_english_coaching.enabled` is true, end complete user-facing replies with the enabled sections below. Include casual chat and ordinary status updates only when `include_casual_chat` is true:

- `书面` gives a natural American-English version suitable for email, documentation, or a formal decision.
- `口语` gives the way an American speaker would naturally say it in conversation.
- `地道用法` highlights 1–3 useful words, collocations, sentence patterns, or tone choices and briefly explains why they sound native.

Translate intent rather than Chinese word order. If the operator writes in English, polish it instead of translating it. Keep the note concise and never delay or replace the actual project response. Tool-progress commentary does not need the repeated note.

When `audio_playback.enabled` is also true, branch on `provider`:

- `host_builtin`: provide the configured written/spoken text and rely on the host's built-in voice or read-aloud control. Do not generate files, claim autoplay, or claim that a Skill can programmatically create a per-sentence native player unless the host exposes and confirms that capability.
- `auto` or `macos_say`: invoke `scripts/render_english_audio.py` once for each enabled `written` or `spoken` sentence and attach every returned `ready` path separately using the host's local-audio rendering syntax. Never combine the two clips.

A `text_only` result preserves the textual note, does not block the main work, and must not be redirected to a different storage root.

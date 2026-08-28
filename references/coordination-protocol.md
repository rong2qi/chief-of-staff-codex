# Coordination protocol

Use this protocol for durable Codex tasks and temporary multi-agent meetings.

## Execution contract

Send each role one decision-complete contract:

```markdown
Role: <job title>
Why needed: <coordination value>
Parent task: <task id or Chief>
Phase: <phase id and objective>
Management depth: 2 | 3
Goal: <observable outcome>
Evidence: <verified inputs and locations>
Scope: <included work>
Non-scope: <excluded work>
Risk: low | medium | high
Write surface: <exclusive files/records/targets, or read-only>
Deliverable: <artifact or conclusion>
Acceptance checks: <commands or observable checks>
Dependencies: <predecessors and required inputs>
Prohibited changes: <protected surfaces and actions>
Approval boundary: <actions requiring the user>
Coordination peers: <registered task IDs and bounded purpose, or none>
Meeting permission: enabled | disabled; max participants: <n>
```

## Routing

- Low risk, clear acceptance, one write surface: one task and one relevant check.
- Medium risk or uncertain cross-file work: read-only scout → sole implementer → read-only verifier.
- High risk, public interface, migration, security, data, or unresolved design: read-only arbiter → sole implementer → independent read-only review.
- At most three active stages. At most two proposal/objection rounds. One concrete defect permits one repair and one re-check.

Use Luna for read-only exploration and routine verification, Terra for the sole implementation writer, and Sol for high-risk arbitration or review. Runtime availability and the user's explicit model choice override this default.

## Goal confirmation and completion

Before implementation, the Chief proposes and asks the user to confirm the final goal, deliverables, acceptance criteria, non-goals, and constraints. Store the request as `goal_confirmation` and keep `project_status: awaiting_goal`. A new project permits only read-only discovery that materially helps clarify the goal. During migration, already-running non-high-impact tasks may finish, but no new task or phase starts before confirmation.

After confirmation, classify the project before creating another phase or task. Apply [product-discovery-governance.md](product-discovery-governance.md). A `coordination_only` project records a concrete exemption and may create coordination work only. A `deliverable_project` appoints one Product Manager depth-2 phase lead and completes the four-lane product-discovery gate before creating or starting production execution. Immediately before production task creation, run the initializer's `--check`; a nonzero result is a hard stop.

The Product Manager manages project initiation, requirements analysis, market research, and advisory architecture feasibility through depth-3 temporary helpers that cannot delegate. If the runtime lacks subagents, the Product Manager completes the four lanes itself and records the limitation without dropping any artifact or evidence requirement. Product discovery cannot bind the later Technical Lead's architecture, bypass the Creative Director, invent market/user evidence, or authorize outreach, paid/restricted data, or another protected action.

After the applicable gate passes or exemption validates, create the next ordered phase and start at least one current-phase task. Completing a phase never completes the project by itself. Set `project_status: completed` only when every final acceptance criterion is `verified` and has non-empty evidence.

While the project is unfinished, keep an active or queued phase task unless the project is explicitly `awaiting_user` or verifiably `blocked`. If every task stops before final acceptance, dispatch the next safe in-scope phase immediately.

When the projected continuation policy is `advance_best_safe_in_scope_path`, select and execute the strongest evidence-backed safe in-scope continuation without opening an operator choice. Do not offer stopping, preserving a failed state, or delaying as peer options while such a path exists. Escalate only when continuing itself requires a new permission or a new Chief. Ordinary failure remains Chief-owned while a bounded diagnostic, repair, or verification path remains. The policy does not authorize production before the product gate, protected actions, bypassed visual selection, concealed safety evidence, transferred ownership, or expanded goals.

## Durable task naming and state

Ordinary Chiefs default to unpinned. Only a mandatory core or operator-approved optional lineage inherits a pin. For its migration or takeover, apply [pin-inheritance-governance.md](pin-inheritance-governance.md): before final `MIGRATION_READY`, authority changes, or predecessor archival, require bundle parity, live automation parity, and applicable pin parity, then independently call `list_threads` and require the successor's exact task ID in `pinnedThreads`. A pin operation receipt is not proof; failed verification cannot transfer control. An ordinary unapproved Chief's unpinned state is not a failure and never creates a replacement.

Title every durable Chief task `Chief of <domain or project>｜<optional local-language label>`. The exact `Chief of ` prefix is mandatory; only the registered global general-office and TODO roles are exceptions. A user-supplied Chinese or informal Chief name belongs after `｜` and does not waive the prefix. Title non-Chief durable child tasks `职务｜工作内容`, for example `技术负责人｜支付架构决策`.

Resolve the Chief's saved Codex `projectId` before creation and use the same project target for every durable child. Verify and record the child's `project_id`. If no saved project is available, use temporary subagents; ask the user to select or save a project before creating a durable child. Do not silently leave durable tasks projectless.

Add a registry entry as soon as creation succeeds. Update it when status, ownership, result, blocker, or task cursor changes. Task status is one of `queued`, `running`, `needs_attention`, `completed`, `failed`, or `archived`.

Depth 1 is the Chief, depth 2 is a phase lead, and depth 3 is an execution role. A phase lead may create depth-3 durable tasks only when its delegated contract explicitly authorizes task creation. Temporary subagents at depth 3 are bounded helpers and cannot create durable roles. Depth 4 or deeper requires a pending `depth_expansion` request and explicit user approval before creation. The Chief remains the sole writer of central project state.

For every active phase, monitor all known task IDs with bounded waits. When one task completes, fails, or needs attention, immediately snapshot all active task IDs, then update the registry and phase plan from the complete result set. This prevents the first event from hiding simultaneous progress and ensures an idle phase is either advanced, blocked with evidence, or escalated with an exact decision.

Active durable children may appear in Recents as independently resumable tasks. Keep them visible while queued, running, failed, or needing attention. After a final handoff has been approved by the configured review route and no retry or dependent follow-up remains, archive the child and mark its registry status `archived`. Under `exception_only`, the Chief may approve a routine child handoff; final project completion still belongs to the operator. Preserve identifiers, cursor, evidence, and summary; archiving is reversible and is not deletion.

## Peer-to-peer coordination

The Chief adds symmetric `coordination_with` task-ID edges only for durable roles in the same verified project. A registered peer may send a direct coordination message containing: a stable coordination ID, purpose, relevant evidence, interface or dependency, exact response needed, and stopping condition. The receiver answers the sender, and the synthesis owner sends the outcome or unresolved conflict to the Chief.

Routine peer coordination does not require user approval and does not count as a milestone report. It cannot change scope, transfer a write surface, approve a handoff, or authorize a protected action. If peers disagree about an interface or ownership, both pause the affected implementation surface and give the Chief their evidence and alternatives. If direct task messaging is unavailable, use the Chief as a relay without changing the protocol.

## Temporary subagent meeting

When enabled, any durable role may convene a meeting of at most `max_meeting_participants` temporary subagents. Define one question, non-overlapping participant roles, shared inputs, read-only defaults, expected evidence, synthesis owner, and stopping condition. Use one implementation writer only when implementation is explicitly part of the meeting; every other participant stays read-only.

Participants may exchange evidence through the parent or runtime messaging tools, but they cannot create durable tasks or another management layer. The parent waits for every requested participant, reconciles findings by evidence rather than vote, and sends one outcome to registered affected peers and the Chief. Limit deliberation to two proposal/objection rounds and one independent verification; otherwise escalate the unresolved choice to the Chief.

## Report review modes

The approval queue supports `goal_confirmation`, `report_review`, and `depth_expansion`. `project.json.report_review_mode` is authoritative:

- `all_reports`: every milestone report and final handoff requires operator review through the Chief task.
- `exception_only`: the Chief reviews routine child progress and final handoffs. Operator review is required only for goal confirmation, a material product decision, a visual decision through the Creative Director, a protected action, safety/security judgment, scope or write-ownership conflict, failed or unverifiable acceptance, depth expansion, or final project completion.

`report_approval_required` is retained for compatibility and must equal `true` only for `all_reports`. Routine commentary never opens a gate.

When `governance_model.mode` is `chair_led_cabinet`, preserve the same exception categories but route them by constitutional channel:

- routine evidence review: `CHIEF_REVIEW_READY` to the project Chief;
- non-visual statutory exception: `CHAIR_BRIEF_READY` to the configured general office;
- visual decision: preview packet to the configured Creative Director;
- operator-facing attention: `USER_ACTION_REQUIRED` may be emitted only by the appropriate hub after deduplication and compression.

TODO scans only the general office and Creative Director as authoritative decision sources. It ignores source-project copies and child-task requests. Emergency bypass is limited to Chief safety violations, concealed protected-action risk, or a conflict in which the Chief is a party.

The child task must:

1. Generate a stable `request_id` as `<task_id>:<report_sequence>` and include it in the handoff.
2. State whether the report is `progress` or `final`, the decision requested, verified evidence, risks, and proposed next action.
3. State `review_route: chief` for routine evidence review or `review_route: operator` with one exact exception category and evidence. A child may propose but cannot self-authorize the route; the Chief verifies it.
4. Under `exception_only`, end routine handoffs with `CHIEF_REVIEW_READY: <request_id>` and do not open a human-attention request. For a verified exception, use the host's blocking input mechanism or `USER_ACTION_REQUIRED: <request_id>`. Under `all_reports`, use the blocking mechanism or legacy `REVIEW_REQUIRED: <request_id>`.

Under enabled `chair_led_cabinet`, replace the direct non-visual `USER_ACTION_REQUIRED` in step 4 with `CHAIR_BRIEF_READY: <request_id>` addressed to the general office. Only the general office can turn it into an operator-facing request. Visual requests follow the Creative Director route instead.

The Chief owns `.chief-of-staff/approval-queue.json`; children never write it. When any watched task completes or needs attention, snapshot all active tasks with a zero-timeout wait before processing results. Insert every unseen report into the queue with `reviewer`, `review_route`, decision basis, and evidence references. This sweep-and-deduplicate rule prevents simultaneous reports from being lost when only one task wakes the wait.

For `exception_only`, the Chief verifies that the report stayed in scope, touched only its owned surface, passed stated acceptance checks, contains no conflicting evidence, and triggers no exception. It then records an explicit Chief approval or sends `退回修改 <request_id>: <reason>` to the child. If an exception applies, the Chief records `review_route: operator`, emits one exact `USER_ACTION_REQUIRED`, and waits. For `all_reports`, every milestone/final report follows that operator path. Silence and unrelated messages never count as operator approval.

Approving a report acknowledges that handoff; it does not authorize any protected action listed in `approval_required`. Request those permissions separately immediately before the action.

## Handoff response

Every delegated task ends with:

```markdown
## Handoff
- 汇报编号：<task_id>:<report_sequence>
- 汇报类型：progress | final
- 已验证事实：...
- 推断：...
- 待确认项：...
- 修改内容：...
- 验收证据：...
- 风险：...
- 建议下一步：...
- 建议审查路径：Chief 自动审查 | 妈妈决定
- 升级原因：无 | <exception category and evidence>
- 审查标记：CHIEF_REVIEW_READY: <request_id> | USER_ACTION_REQUIRED: <request_id>
```

Read-only roles must state `修改内容：无`. A writer lists only its owned changes. The Chief of Staff reconciles disagreements against evidence; it does not decide by majority vote.

## Escalation

Escalate to the user only for:

- deletion or materially destructive operations;
- production, release, payment, or external-message actions;
- permission or access expansion;
- security or safety risks needing human judgment;
- a product choice with meaningfully different outcomes that evidence cannot resolve;
- final project acceptance and completion.

If the same blocker survives the initial attempt plus two focused follow-ups, reassess the remaining safe in-scope paths. Under the enabled continuation policy, continue with the strongest evidenced alternative; stop and report only when no safe authorized path remains or continuing itself requires a new permission or a new Chief. Otherwise report evidence, attempted remedies, and the exact decision needed.

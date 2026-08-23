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

After confirmation, create an ordered phase plan and start at least one current-phase task. Completing a phase never completes the project by itself. Set `project_status: completed` only when every final acceptance criterion is `verified` and has non-empty evidence.

While the project is unfinished, keep an active or queued phase task unless the project is explicitly `awaiting_user` or verifiably `blocked`. If every task stops before final acceptance, dispatch the next safe in-scope phase immediately.

## Durable task naming and state

Title every durable child task `职务｜工作内容`. Keep the role short and make the work content outcome-oriented, for example `技术负责人｜支付架构决策`.

Resolve the Chief's saved Codex `projectId` before creation and use the same project target for every durable child. Verify and record the child's `project_id`. If no saved project is available, use temporary subagents; ask the user to select or save a project before creating a durable child. Do not silently leave durable tasks projectless.

Add a registry entry as soon as creation succeeds. Update it when status, ownership, result, blocker, or task cursor changes. Task status is one of `queued`, `running`, `needs_attention`, `completed`, `failed`, or `archived`.

Depth 1 is the Chief, depth 2 is a phase lead, and depth 3 is an execution role. A phase lead may create depth-3 durable tasks only when its delegated contract explicitly authorizes task creation. Temporary subagents at depth 3 are bounded helpers and cannot create durable roles. Depth 4 or deeper requires a pending `depth_expansion` request and explicit user approval before creation. The Chief remains the sole writer of central project state.

For every active phase, monitor all known task IDs with bounded waits. When one task completes, fails, or needs attention, immediately snapshot all active task IDs, then update the registry and phase plan from the complete result set. This prevents the first event from hiding simultaneous progress and ensures an idle phase is either advanced, blocked with evidence, or escalated with an exact decision.

Active durable children may appear in Recents as independently resumable tasks. Keep them visible while queued, running, failed, or needing attention. After an explicitly approved final handoff has been recorded and no retry or dependent follow-up remains, archive the child and mark its registry status `archived`. Preserve identifiers, cursor, evidence, and summary; archiving is reversible and is not deletion.

## Peer-to-peer coordination

The Chief adds symmetric `coordination_with` task-ID edges only for durable roles in the same verified project. A registered peer may send a direct coordination message containing: a stable coordination ID, purpose, relevant evidence, interface or dependency, exact response needed, and stopping condition. The receiver answers the sender, and the synthesis owner sends the outcome or unresolved conflict to the Chief.

Routine peer coordination does not require user approval and does not count as a milestone report. It cannot change scope, transfer a write surface, approve a handoff, or authorize a protected action. If peers disagree about an interface or ownership, both pause the affected implementation surface and give the Chief their evidence and alternatives. If direct task messaging is unavailable, use the Chief as a relay without changing the protocol.

## Temporary subagent meeting

When enabled, any durable role may convene a meeting of at most `max_meeting_participants` temporary subagents. Define one question, non-overlapping participant roles, shared inputs, read-only defaults, expected evidence, synthesis owner, and stopping condition. Use one implementation writer only when implementation is explicitly part of the meeting; every other participant stays read-only.

Participants may exchange evidence through the parent or runtime messaging tools, but they cannot create durable tasks or another management layer. The parent waits for every requested participant, reconciles findings by evidence rather than vote, and sends one outcome to registered affected peers and the Chief. Limit deliberation to two proposal/objection rounds and one independent verification; otherwise escalate the unresolved choice to the Chief.

## Report approval gate

The approval queue supports `goal_confirmation`, `report_review`, and `depth_expansion`. When `.chief-of-staff/project.json` sets `report_approval_required` to `true`, every milestone report and final handoff requires human review through the Chief task. Routine commentary does not open a gate.

The child task must:

1. Generate a stable `request_id` as `<task_id>:<report_sequence>` and include it in the handoff.
2. State whether the report is `progress` or `final`, the decision requested, verified evidence, risks, and proposed next action.
3. Use the host's blocking user-input or review-request mechanism, when available, to request `批准` or `退回修改`. This should place the Codex task in a needs-attention state. Do not continue dependent work while the gate is pending.
4. If no native request mechanism is available, end the handoff with `REVIEW_REQUIRED: <request_id>` so the Chief can create the human-review request in the main task.

The Chief owns `.chief-of-staff/approval-queue.json`; children never write it. When any watched task completes or needs attention, snapshot all active tasks with a zero-timeout wait before processing results. Insert every unseen report into the queue, set its registry status to `needs_attention`, and batch all pending requests into one numbered user prompt. This sweep-and-deduplicate rule prevents simultaneous reports from being lost when only one task wakes the wait.

The user remains in the Chief task. After the user decides, the Chief sends an explicit `批准 <request_id>` or `退回修改 <request_id>: <reason>` message to the child, records the decision, and advances the registry status. No response, silence, a newer unrelated message, or the Chief's own judgment counts as approval.

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
- 批复请求：批准 | 退回修改
```

Read-only roles must state `修改内容：无`. A writer lists only its owned changes. The Chief of Staff reconciles disagreements against evidence; it does not decide by majority vote.

## Escalation

Escalate to the user only for:

- deletion or materially destructive operations;
- production, release, payment, or external-message actions;
- permission or access expansion;
- security or safety risks needing human judgment;
- a product choice with meaningfully different outcomes that evidence cannot resolve.

If the same blocker survives the initial attempt plus two focused follow-ups, stop and report evidence, attempted remedies, and the exact decision needed.

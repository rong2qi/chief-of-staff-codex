# Coordination protocol

Use this protocol for durable Codex tasks and temporary multi-agent meetings.

## Execution contract

Send each role one decision-complete contract:

```markdown
Role: <job title>
Why needed: <coordination value>
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
```

## Routing

- Low risk, clear acceptance, one write surface: one task and one relevant check.
- Medium risk or uncertain cross-file work: read-only scout → sole implementer → read-only verifier.
- High risk, public interface, migration, security, data, or unresolved design: read-only arbiter → sole implementer → independent read-only review.
- At most three active stages. At most two proposal/objection rounds. One concrete defect permits one repair and one re-check.

Use Luna for read-only exploration and routine verification, Terra for the sole implementation writer, and Sol for high-risk arbitration or review. Runtime availability and the user's explicit model choice override this default.

## Durable task naming and state

Title every durable child task `职务｜工作内容`. Keep the role short and make the work content outcome-oriented, for example `技术负责人｜支付架构决策`.

Add a registry entry as soon as creation succeeds. Update it when status, ownership, result, blocker, or task cursor changes. Task status is one of `queued`, `running`, `needs_attention`, `completed`, `failed`, or `archived`.

## Report approval gate

When `.chief-of-staff/project.json` sets `report_approval_required` to `true`, every milestone report and final handoff requires human review through the Chief task. Routine commentary does not open a gate.

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

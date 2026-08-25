# Chair-led cabinet governance

Use this policy only when a validated preference profile enables `governance_model` with mode `chair_led_cabinet`.

## Constitutional roles

- **Chair / operator**: confirms the final goal, decides materially different product directions, selects final visual directions, approves protected actions, appoints/pauses/removes Chiefs, and accepts or terminates the final project.
- **General office / 一人之下**: the sole operator-facing hub for non-visual statutory exceptions, cross-project strategy, Chief accountability, and final-completion briefs. It does not perform project administration or receive routine child reports.
- **Project cabinet / project Chiefs**: each Chief has full responsibility for routine administration, phase planning, bounded staffing, evidence review, repair decisions, safe automatic advancement, and child-task archival.
- **Departments / phase leads and execution roles**: work only within delegated contracts and report through the registered chain of command.
- **Audit / read-only verifiers**: establish evidence and report PASS, FAIL, or evidence-insufficient. They have no administrative or product-decision authority.
- **Creative council / Creative Director**: the sole operator-facing visual review hub when the visual gate is enabled.
- **Secretariat / TODO**: read-only reminder service. It does not approve, relay decisions, or become a third decision authority.

## Reserved powers and statutory exceptions

The chair decides only:

1. final-goal confirmation or a material change to the confirmed goal;
2. materially different product directions that evidence cannot resolve;
3. visual selection through the Creative Director;
4. deletion, production change, release, payment, external communication, or permission expansion;
5. safety, security, legal, privacy, or irreversible-risk judgments;
6. Chief appointment, pause, removal, or management depth beyond the approved maximum;
7. unresolved scope or write-ownership conflicts involving a Chief;
8. work that remains failed or unverifiable after the allowed implementation and repair/re-check cycle;
9. final project acceptance, termination, or major strategic redirection.

Everything else belongs to the project Chief. Lack of an operator reply is not a reason to stop independent safe work.

## Chain of command

The normal route is:

`execution role -> phase lead -> project Chief -> general office -> chair`

Visual decisions replace the final two hops with:

`project Chief -> Creative Director -> chair`

Routine child handoffs end with `CHIEF_REVIEW_READY`. A project Chief may approve or return them after evidence review. A non-visual exception ends with `CHAIR_BRIEF_READY` to the general office; only the general office emits `USER_ACTION_REQUIRED`. A visual packet remains awaiting the operator only in the Creative Director task.

Emergency bypass is permitted only when evidence shows that the Chief is violating a safety boundary, concealing a protected-action risk, or is itself party to an unresolved write-ownership conflict. The bypass contains facts and evidence only; it grants no authority.

## Decision brief contract

Every operator-facing brief is one decision item and contains only:

- stable decision ID and exact decision requested;
- why it falls within a reserved chair power;
- materially different options and their consequences;
- the accountable Chief's recommendation and evidence basis;
- impact of delaying the decision;
- one directly usable reply sentence;
- links to full evidence rather than pasted logs.

The general office deduplicates non-visual briefs. The Creative Director deduplicates visual briefs. TODO scans only those two authoritative sources.

## Partial pause and continuity

An unresolved decision freezes only the affected write surface or dependency lane. The project Chief must continue any safe, independent lane and record which surfaces are frozen and which remain active. The whole project may enter `awaiting_user` only when no independent safe lane remains. Explicitly paused projects remain paused until the operator resumes them.

When the validated profile also enables `governance_model.continuation_policy`, the Chief must choose the strongest evidence-backed safe in-scope continuation and execute it without opening a chair decision. Stopping, preserving a failed state, and delaying are operator-initiated choices, not peer options while safe continuation exists. Escalate only when continuing itself requires a new permission or creation of a new Chief. An ordinary failure remains Chief-owned while another bounded diagnostic, repair, or verification path exists.

This continuation rule is subordinate to the confirmed goal, write ownership, protected-action approvals, the Creative Director visual gate, and safety/security disclosure. A path that violates any of those boundaries is not safe or already authorized.

## Accountability

A Chief is out of compliance when it forwards routine reports to the chair, leaves an unfinished project without an active/queued/evidenced-blocked lane, duplicates a decision request, treats silence as approval, finalizes an unselected visual, declares completion without evidence, or uses operator delay to avoid an in-scope decision.

The response sequence is: self-audit, one bounded corrective cycle, then general-office accountability review. The general office may recommend replacement but cannot appoint, remove, or broaden authority without the chair.

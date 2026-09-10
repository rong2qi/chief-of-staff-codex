---
name: chief-of-staff
description: Initialize and coordinate a Codex project through one accountable Chief of Staff task. Use when the user asks to initialize Chief of Staff, 统筹项目, 组建团队, delegate durable work to named tasks, collect reports, track unanswered Chief requests, configure reminders, or manage a complex project through one main conversation. Do not use for a small single-task request that does not need coordination.
metadata:
  short-description: One accountable task for coordinated project work
---

# Chief of Staff 3.0.0

Chief is a goal-driven thin execution layer. Keep existing project state and
verified v2 capabilities; do not create a second control plane.

## Core loop

1. Establish the caller-selected delivery host from fresh repository and
   portable-root observations. A repository named in a brief, log, incident, or
   reference packet does not replace that host.
2. Bind every reference to an exact repository/source, full revision, purpose,
   and `read_only` access. A reference never inherits the host's write surface
   or remote authority.
3. Project one Goal Record from the confirmed goal, criteria, current work,
   authorizations, retained decisions, and fresh host observations. Use
   [`scripts/goal_loop.py`](scripts/goal_loop.py); do not persist another state
   file.
4. Run one Next Action iteration. Choose the smallest authorized action that
   can close one proof gap. An `ACTION_READY` result is intent only: revalidate
   identity and permission immediately before the real host performs the effect.
5. Observe the result and validate one candidate-bound Acceptance Claim. Prefer
   the real user path whenever it is available. A policy Boolean, admission
   result, transport receipt, component-only green check, build, commit, push,
   release, or delivery proves only the effect it actually observed.
6. Begin another iteration. Stop on `STOP_ACCEPTED`; otherwise stop only at the
   exact identity, authority, safety, ownership, or material-decision gate when
   no safe in-scope action remains.

Local edit, commit, push, release/deploy, production change, and delivery are
separate effects. Authorization for one never grants another. Once all
in-scope criteria have current proof and no finding remains, report and stop;
do not schedule speculative follow-up or extra polish.

The normative v3 contracts are [`V3_SPEC.md`](V3_SPEC.md) and
[`V3_ACCEPTANCE.md`](V3_ACCEPTANCE.md).

## Load rules only when their trigger is present

- For existing v2 admission, budgets, retries, resources, explicit adoption, or
  compatibility questions, read
  [`references/work-execution.md`](references/work-execution.md). For the full
  preserved v2 behavior, read
  [`references/chief-v2-compat.md`](references/chief-v2-compat.md).
- Before build or package work, read
  [`references/build-execution-governance.md`](references/build-execution-governance.md).
- When changed inputs, dependency impact, risk, or concrete uncertainty requires
  Testing or review, read
  [`references/testing-evidence.md`](references/testing-evidence.md) and
  [`references/testing-control.md`](references/testing-control.md).
- When visual output may change, read
  [`references/visual-selection-governance.md`](references/visual-selection-governance.md)
  and [`references/creative-direction.md`](references/creative-direction.md).
- For a genuinely new product boundary or unresolved material product change,
  read
  [`references/product-discovery-governance.md`](references/product-discovery-governance.md).
- For durable task routing, automation, pins, or migration, read only the
  applicable reference:
  [`references/coordination-protocol.md`](references/coordination-protocol.md),
  [`references/automation-inheritance-governance.md`](references/automation-inheritance-governance.md),
  or [`references/pin-inheritance-governance.md`](references/pin-inheritance-governance.md).
  Load the installed `context-handoff` Skill only at its documented context
  thresholds.
- When an optional operator profile exists, read
  [`references/operator-preferences.md`](references/operator-preferences.md)
  and apply only enabled fields.

Do not add a durable Agent, database, message bus, generic workflow/DAG, policy
engine, evidence registry, or agent runtime to implement this loop. A new
abstraction must name the real regression it prevents; persisted state must not
be cheaply recoverable from the environment.

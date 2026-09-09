# Risk-based, non-blocking Testing — v2.0.2

## Decision rule

Testing is triggered by **new risk**, not by a new file, commit, candidate,
freeze, phase, merge, or integration label. Reuse valid evidence until a tested
input, asset, contract, dependency, or risk scope invalidates it. Run
`testing_evidence.py plan` first, then `testing_control.py decide`; send only the
returned `testing_request`. A request without a changed input, dependency impact,
or explicit new risk is a policy error and remains local.

Cheap-first means: exact candidate SHA, accepted task scope, recorded evidence,
Git changed paths, and declared dependency metadata. Do not build a whole-repo
dependency graph merely to avoid a short check. If evidence is uncertain, look
up retained evidence, inspect changed scope, and choose the smallest targeted
validation. Escalate uncertainty to independent Testing only when a concrete
new risk remains; use a synchronous gate only for L3 or an explicit
`SYNC_TESTING_REQUIRED` contract.

Every outgoing request includes `TESTING_JUSTIFICATION_V1` with current SHA,
prior tested SHA/evidence ID, changed paths/assets, dependency impact, new risk,
invalidated evidence, requested scope, and why deterministic/local evidence is
insufficient. Candidate creation alone cannot populate that justification.

## Risk levels and completion

| Level | Default validation | Testing behavior |
| --- | --- | --- |
| `L0` deterministic/mechanical | File/manifest existence, readability, discovery and minimal load or another exact local check | No independent Testing round trip |
| `L1` low-risk local | Targeted self-test plus existing automated checks | Local by default; asynchronous targeted Testing only for an identified risk not covered locally |
| `L2` business behavior | Evidence inheritance plus delta validation for the new behavior risk | Targeted, non-blocking while unrelated work remains |
| `L3` high-risk/irreversible/production-critical | Evidence inheritance plus independent targeted validation | Synchronous gate blocks only the dangerous action |

`LOCAL_CHECK_PASS`, `SELF_TEST_PASS`, and `INHERITED_PASS` are exact evidence
labels, not synonyms for `TESTING_GATE_PASS`. A locally complete candidate may be
`LOCAL_CANDIDATE_READY / TESTING_PENDING` or
`LOCAL_CANDIDATE_READY / TESTING_INFRA_ERROR`. Both permit work that does not
depend on the verdict. Only a real current-candidate `TESTING_GATE_PASS` can be
reported as “Testing passed.”

## Evidence inheritance and integration

Use [the evidence model](testing-evidence.md) to classify each accepted test:

- `INHERITED_PASS`: tested paths/assets, contracts, definitions, and relevant
  dependency fingerprints are unchanged and the original PASS remains valid.
- `RETEST_REQUIRED`: a tested input changed, a dependency impacts the scope, a
  contract behavior changed, or retained evidence is explicitly invalidated.
- `INTEGRATION_ONLY`: passed parts are unchanged but their first composition
  creates a wiring/shared-state risk. Run one minimal integration smoke.

Integration never means “invalidate all.” Look up evidence, diff exact commits,
map dependency impact, inherit unaffected PASS, retest only the delta, and add a
minimum combination smoke when warranted. The v2 evidence record adds identity,
timestamp, result, risk scope and tested path/asset metadata; v1 frozen evidence
remains readable and needs no project-state migration.

## Event semantics and priority

Filter telemetry before high-cost reasoning. `*_ACK`, `*_RECEIVED`, `*_QUEUED`,
`*_STARTED`, `*_READY`, `*_HEARTBEAT`, `*_PROGRESS`, and retry status perform
`record_state(); return`. They do not open a reasoning turn, wait, retry, change
the work queue, or produce a user-facing status message.

Decision events are `TESTING_GATE_PASS`, `TESTING_GATE_FAIL`,
`TESTING_INFRA_ERROR`, and `TESTING_SCOPE_CHANGED` with a nonempty new-risk
description. A scope-update ACK is telemetry. `USER_DECISION`,
`IMPLEMENTER_COMPLETED`, `BUILD_FAILED`, `BUILD_SUCCEEDED`, and real Testing
verdicts all outrank telemetry. Event order is stable within a priority class.

During an APK build critical path, ordinary Testing telemetry remains record-only.
Only failures directly affecting APK generation/parseability, package,
version, frozen signing identity, or actual runtime integration can block the
APK-only path. AAB-only, marketing, visual-governance and ordinary ACK/READY
events cannot block it. The build executor preserves declared APK bytes before
postchecks; non-APK gates cannot delete a preserved APK.

## Pending, retries, and infrastructure errors

`TESTING_PENDING` is not `WAIT`. Continue cheap checks, other implementation,
candidate freeze, local commit preparation and independent modules. A whole
project waits only when every remaining action truly depends on the same
synchronous L3/explicit gate.

One Testing delivery gets one automatic retry after an empty item list, missing
report, timeout, transport failure, or abnormal turn end. A second infrastructure
failure becomes `TESTING_INFRA_ERROR`; stop delivery retries. It is not
`TESTING_GATE_FAIL` and does not roll back a completed L0/L1 deterministic task.
Only a real candidate finding produces Gate Fail.

## Creative fast loop

Use `implement → creative review → render → compare → adjust` for high-frequency
visual refinement. Batch revisions and evaluate Testing once at a meaningful
candidate boundary. Trigger a delta request only when the batch changes frozen
structure/business behavior, introduces a new asset license/provenance risk,
changes runtime integration, or identifies another concrete risk. A boundary is
a cadence point, not by itself a risk. Testing round trips therefore do not grow
1:1 with visual revision count.

## Executable policy and dogfood

`scripts/testing_control.py` exposes `events`, `decide`, `delivery`, `schedule`,
`creative`, and `dogfood` commands over JSON requests. It classifies and returns
intents only; it never runs tests, sends messages, installs, builds, issues PASS,
or authorizes promotion. The five v2.0.x incident replays live in
`tests/fixtures/testing-control-v2.0.2.json` and use the same policy functions as
normal evaluation.

Architecture limit: this source repository cannot intercept a host's native task
delivery before the host wakes the model. A host adapter must route Testing event
envelopes through the classifier to obtain true pre-reasoning filtering. When the
model already received the envelope, Chief performs only the classifier call and
records telemetry without a follow-on reasoning/scheduling turn. The regression
suite proves this repository boundary; it does not claim an unobserved host patch.

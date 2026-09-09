# Chief repository working agreement

Chief generic behavior lives in `SKILL.md` and `references/work-execution.md`.
Use the pinned release and preserve schema-2 project state and user overrides.

## Evidence-aware, risk-based, non-blocking Testing

Follow `references/testing-evidence.md` and `scripts/testing_evidence.py` for Git
candidate freeze, integration dispatch and acceptance. Follow
`references/testing-control.md` and `scripts/testing_control.py` before sending
or scheduling Testing. Already-passed frozen
evidence is a reusable asset. Phase changes, packaging or integration alone are
not Testing triggers. Compare full candidate commits, actual Git diff, tested
paths/inputs and reviewed dependency closure; require a changed input,
dependency impact or explicit new risk in `TESTING_JUSTIFICATION`.

- `INHERITED_PASS`: authenticated original `TESTING_GATE_PASS`, matching evidence
  hash, unchanged scope/input/dependency fingerprints, no transitive impact.
- `RETEST_REQUIRED`: direct/dependency impact, fingerprint mismatch, changed
  contract or explicitly invalidated evidence. Resolve uncertainty cheap-first;
  only a concrete remaining risk can create a Testing request.
- `INTEGRATION_ONLY`: minimal combination-only wiring/shared-state smoke.

L0 uses deterministic local checks; L1 stays local by default; L2 is targeted
and non-blocking; L3 or explicit `SYNC_TESTING_REQUIRED` blocks only its dangerous
action. `*_ACK`, `*_READY`, `*_STARTED`, `*_RECEIVED`, heartbeat and progress are
record-only telemetry. `TESTING_PENDING` and `TESTING_INFRA_ERROR` never idle
unrelated runnable work. Retry an empty/missing/timeout delivery once, then stop
with infra error rather than product failure. Send only the generated
`testing_payload` plus justification to Testing; keep the complete impact map
and provenance in the local handoff audit. Revalidate with `accept` before
acceptance. `DELTA_GATE_READY` is evidence readiness, not authority to mint a new
Testing gate, publish, push or deploy. Existing native authority and independent
non-Git activation gates remain binding. Never substitute transport ACK or local
self-check success for `TESTING_GATE_PASS`.

Run the complete Chief regression with `python3 -m unittest discover -s tests`.
Release-source sync requires a clean exact tag checkout; never follow floating
main, overwrite user changes, force-push or rewrite history.

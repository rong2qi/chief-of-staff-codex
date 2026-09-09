# Chief repository working agreement

Chief generic behavior lives in `SKILL.md` and `references/work-execution.md`.
Use the pinned release and preserve schema-2 project state and user overrides.

## Evidence-aware Testing / delta gate

Follow `references/testing-evidence.md` and `scripts/testing_evidence.py` for Git
candidate freeze, integration dispatch and acceptance. Already-passed frozen
evidence is a reusable asset. Phase changes, packaging or integration alone are
not reasons to invalidate all previous tests. Compare full candidate commits,
actual Git diff, tested paths/inputs and reviewed dependency closure.

- `INHERITED_PASS`: authenticated original `TESTING_GATE_PASS`, matching evidence
  hash, unchanged scope/input/dependency fingerprints, no transitive impact.
- `RETEST_REQUIRED`: direct/dependency impact, fingerprint mismatch, missing or
  unverifiable evidence. Uncertainty fails safe to retest; never invent PASS.
- `INTEGRATION_ONLY`: minimal combination-only wiring/shared-state smoke.

Send only the generated `testing_payload` to Testing; keep the complete impact
map and provenance in the local handoff audit. Revalidate with `accept` before
acceptance. `DELTA_GATE_READY` is evidence readiness, not authority to mint a new
Testing gate, publish, push or deploy. Existing native authority and independent
non-Git activation gates remain binding. Never substitute transport ACK or local
self-check success for `TESTING_GATE_PASS`.

Run the complete Chief regression with `python3 -m unittest discover -s tests`.
Release-source sync requires a clean exact tag checkout; never follow floating
main, overwrite user changes, force-push or rewrite history.

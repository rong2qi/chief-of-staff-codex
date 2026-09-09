# Chief v2.0.1 Evidence-aware Testing implementation plan

Goal: reuse authenticated frozen Testing evidence by exact Git inputs and dependency impact, with fail-safe delta-only dispatch.

Architecture: one `scripts/testing_evidence.py` boundary implements subject snapshots, authenticated freeze, delta planning and handoff acceptance. Reuse native receipt verification from `continuous_execution`, safe retained-file reads from `retry_policy`, and private Testing authority. Project schema remains 2; evidence uses its own versioned additive format.

## Audit and decisions

- `continuous_execution.validate_native_testing_return`: native coordinator, Testing identity, package/candidate/policy binding already exist. Reuse; neither a forwarded PASS nor a hash alone authenticates Testing.
- `delivery_ledger`: ARTIFACT_FROZEN and ACK are transport states, not Testing. Retain separation. Delta CLI produces the exact review payload and acceptance material for that transport.
- `work_execution`: existing per-check input hashes and retained file checks are local integrity, not native Testing. Do not relabel these as inherited evidence.
- `chief_sync`: source release fixed to 2.0.0; allow explicitly supported 2.0.1 with exact matching tag, preserve dirty/conflict and fleet behavior.
- `assets/chief-project-entry.md`: thin generic source link. Add the new contract; leave historical full template bytes intact because sync recognizes it as a migration preimage.
- `context-handoff`, activation and legacy AGENTS gates: independently gated non-Git artifacts retain their exact-hash gates. Do not silently translate a manifest digest into a Git SHA.

## Execution

- [x] Add real Git fixture tests for unchanged/unrelated/direct/dependency/shared-interface changes, multi-source integration, missing/altered/forged native evidence, audited handoff acceptance and release sync.
- [x] Implement strict candidate IDs, NUL-delimited Git tree/diff observations, explicit reviewed dependency closure, authenticated subject freeze and hash integrity. Include additions, removals, modes and symlinks; unsupported inputs fail closed.
- [x] Implement impact map, transitive dependency propagation, delta-only Testing payload, minimum integration smoke and fresh acceptance revalidation. No automatic Testing PASS issuance.
- [x] Update current README, thin AGENTS and Chief work protocol, add schema/CLI examples and audit limits; version 2.0.1/schema 2.
- [x] Run full `python3 -m unittest discover -s tests`, inspect failures, inspect diff and release metadata. Verify sensitive negative cases reject a credible bypass.
- [ ] Recheck remote main/tag, commit on isolated main with Chinese-first message, create annotated tag, atomic ordinary fast-forward push main and tag, verify remote peeled tag and main. User explicitly authorized these actions.

No new dependency, installation, project fleet mutation or business test run is needed. This is an existing-repository change using Python stdlib and Git. The user's 16 requirements are the approved scope. Missing dependency closure is uncertainty, never proof of independence. Native observation storage remains a trusted host boundary, as in the existing ledger.

## Review evidence

Read-only review reproduced stale consumer inheritance after fresh provider PASS,
hidden Git index changes, repeated unchanged smoke and malformed observation
handling. Each has a regression and repair. A follow-up found consumer-only
returns needed separate authenticated dependency metadata; `dependency_specs`
now supplies non-executed context without broadening the Testing payload. Final
focused review found no outstanding actionable issue in that repair. This is
code review evidence, not a Testing Chief `TESTING_GATE_PASS` receipt.

The default host `python3` was 3.9.6 and the existing Astra module refused it.
Use the already-installed Python 3.11+ runtime for the full suite; no dependency
installation is needed. Final regression/release receipts are retained in the
delivery report rather than embedding the release's own SHA into its inputs.

Final full regression: Python 3.11.15, 362 tests, 361 passed, one pre-existing optional live-AGENTS input check skipped, zero failures (38.375 seconds). Focused evidence/sync suite: 39 tests passed.

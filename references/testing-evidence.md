# Evidence-aware Testing / delta gate — v2.0.1

## Rule and boundary

Frozen evidence is a reusable asset, not a one-use ticket. Use full source and
current commit SHAs, Git diff and dependency impact. A stage switch alone cannot
invalidate all evidence. This implementation supports tracked Git inputs, files
and whole directories. Directory snapshots include additions, removals, modes
and content; rename detection cannot hide either path. Symlinks, submodules,
missing inputs or incomplete dependency closure cannot prove inheritance.

No new dependencies are required. Python stdlib and Git implement the model.
No test command or network action is executed by the evidence CLI. The command
creates review material; Testing still chooses and executes the smallest checks
that address the reported risks. Arbitrary test commands in evidence are never
executed. Diff and snapshot identity are stronger than a caller's “unchanged”.

## Model

`CHIEF_TESTING_SUBJECT_V1` binds `candidate_sha`, test definitions and observed
Git tree entries. Each test has these exact fields:

```json
{
  "test_id": "M1-message-search",
  "scope": "Message/search contract and behavior",
  "tested_paths": ["message-search"],
  "tested_inputs": ["contracts/message-search.json", "tests/message-search"],
  "dependency_paths": ["shared/interfaces", "requirements.lock", "test-environment.json"],
  "depends_on": [],
  "dependency_closure_complete": true
}
```

Paths are literal repository-relative POSIX files/directories, not globs. Include
test definitions, fixtures, resources, contracts, build configuration, environment
and dependency locks that affect the claim. Record external environment versions
in a tracked manifest only after observing them, and refresh it when they change.
If external/dynamic inputs cannot be captured reliably, set closure complete to
false and retest. The flag is a scope assertion reviewed by the original Testing
Chief, not an automatic dependency analyzer or permission to omit inputs.
`depends_on` names other test IDs in the current required test inventory; missing
IDs, cycles and transitive invalidation force retest. The current inventory must
come from the accepted work contract: deleting a required test is not scope
approval. Changing any test definition invalidates its previous evidence.

Transitive comparisons use the consumer's original candidate, even if a changed
provider has since obtained a fresh PASS. A source bundle missing the named
dependency's reviewed definition/snapshot cannot establish that consumer's
closure. `prepare` accepts optional `dependency_specs` to bind those definitions
and Git snapshots without executing their tests. The delta's top-level
`dependency_specs` supplies preparation context; it is deliberately outside the
Testing execution payload. Only subject `tests` are treated as executed tests;
dependency metadata can never manufacture their PASS. For independently frozen
modules, explicit provider paths in `dependency_paths` are another supported
way to describe the closure.

`CHIEF_FROZEN_TESTING_EVIDENCE_V1` retains the subject, original execution package,
native return observation, gate reference/hash/issuer/status, conclusion and
`evidence_hash`. `observations[test_id]` contains input and dependency snapshots,
`dependency_fingerprint` and definition hash. Fingerprints include Git modes,
object types and blob IDs, keyed by full path. A commit SHA is distinct from the
existing `candidate_sha256`: the latter binds the canonical whole subject digest
in the native Testing execution package. Never put a 40-digit SHA in that field.

## Native authority

Reuse `continuous_execution.validate_native_testing_return` and the host-pinned
`private_authority` configuration. Only the actual Testing Chief's original
`CHIEF_TESTING_GATE_RECEIPT_V1` with `TESTING_GATE_PASS` can freeze reusable
evidence. Direct Chief gates also work for low/medium risk; delegated local PASS
does not become reusable Chief PASS. The original package, scope, candidate
digest, writer, coordinator, native event and issuer bindings are all checked.

The host supplies `--native-root`, disjoint from the submitting repository,
containing original native observations, plus the existing
`CHIEF_PRIVATE_AUTHORITY_CONFIG_PATH` and `CHIEF_PRIVATE_AUTHORITY_CONFIG_SHA256`.
Never provision these from the candidate/request or let the writer populate the
native root. Existing safe descriptor-based retained reads reject traversal,
symlinks, hardlink aliases and changed bytes. Hashes provide integrity, not
cryptographic authorship; authority depends on the host-controlled root and
private configuration, just as in the existing delivery ledger. These commands
never create authority configuration or Testing receipts.

## Freeze → impact map → delta-only dispatch → acceptance

Keep request/output JSON outside the candidate checkout so recording evidence
does not dirty the candidate. The current candidate must be clean and exactly
checked out. Prior candidates must remain available as full Git objects.

1. Prepare a JSON request with `candidate_sha` and the accepted `tests` inventory:

   ```bash
   python3 scripts/testing_evidence.py prepare --repo /project --request /evidence/prepare.json > /evidence/subject.json
   ```

   Output has `subject` and `candidate_sha256`. Submit this exact subject to the
   existing Testing workflow, with that digest in the execution package. Testing
   emits the native gate; do not construct a receipt yourself.

2. Put the exact `subject`, original approved `package`, and `observed` reference
   into `/evidence/freeze.json`. `observed` uses the existing return shape:
   `native_receipt_ref: native://gate.json` and `native_receipt_sha256`.

   ```bash
   python3 scripts/testing_evidence.py freeze --repo /project --native-root /host/native-observations --request /evidence/freeze.json > /evidence/frozen.json
   ```

3. When an integration candidate exists, make a request with its `candidate_sha`,
   accepted `tests`, prior frozen bundles in `evidence`, and `integration: true`
   when composition introduces new wiring/shared-state risk. Multiple source
   commits or a merge candidate also require a minimum combination smoke.

   ```bash
   python3 scripts/testing_evidence.py plan --repo /project --native-root /host/native-observations --request /evidence/integration.json > /evidence/delta.json
   ```

   `impact_map` records per-item source/current SHA, original gate, evidence hash,
   changed paths, fingerprints, attempted inheritance sources and reasons.
   Invalid bundles appear in `rejected_evidence`; their tests default to
   `RETEST_REQUIRED`. Unknown current candidate or malformed required inventory
   yields `EVIDENCE_BLOCKED`/nonzero instead of a misleading successful plan.

   Send **only `testing_payload`**, never the entire delta/request (which retains
   historical bundles for local audit). It contains only `RETEST_REQUIRED` and
   `INTEGRATION_ONLY` definitions. The reserved `integration-smoke` is one minimum
   cross-module wiring/shared-state check, not rerunning all module tests.
   A previously verified smoke with the same combined inventory and inputs is
   itself inherited. If its inputs change, that existing smoke requires retest.
   Retain full audit locally; let Testing consult provenance by reference when
   necessary. Example: M1 and M2 independently pass, shared API unchanged → two
   inherited items, one smoke. API changes → affected consumers retest plus smoke.

4. Prepare/freeze the returned pending scope through the same native Testing
   workflow. In its preparation request copy `tests` from `testing_payload` and
   `dependency_specs` from the delta's top level. This binds non-executed provider
   context so a newly retested consumer can inherit later; it never resubmits the
   provider test. Make an acceptance request with `delta` and the resulting frozen
   bundles in `returns` (empty only when nothing was pending):

   ```bash
   python3 scripts/testing_evidence.py accept --repo /project --native-root /host/native-observations --request /evidence/acceptance.json > /evidence/acceptance-audit.json
   ```

   Acceptance recomputes the original plan, rechecks every source gate and Git
   observation, then requires exact current-candidate coverage of the pending
   scopes. Wrong candidate, broadened/repeated already-inherited scope, duplicate
   returns, missing smoke, altered plan or vanished original receipt all block.
   The result is `DELTA_GATE_READY`, **not** a newly issued `TESTING_GATE_PASS`.
   Retain it with the source Chief's handoff/acceptance evidence. Existing work
   completion and independent gate authority remain in force. Delivery ACK
   remains transport evidence. The Testing Chief can issue its final current
   candidate gate from the validated inherited chain plus delta outcomes.

## Compatibility

Project schema remains **2**, `WORK_EXECUTION_V1` stays unchanged. The new evidence
and delta records have independent V1 schema labels; no destructive migration is
needed. Old self-checks, manifest-only gates and legacy receipts without the
bound Git subject cannot be automatically upgraded: retain them and retest the
unprovable scope. Independently gated activation/non-Git adapters retain their
current exact-hash validation. Historical full AGENTS templates remain unchanged
so existing sync preimage recognition works; current thin AGENTS points here.

Sync/fleet-sync supports exact `v2.0.0` and `v2.0.1` source tags, validates schema
and migration only, and preserves business files, work history and user overrides.
Updating Chief itself is not a reason to rebuild or retest every business module.
If an adopted Chief change affects a particular validation rule, declare that
dependency and invalidate only the affected evidence. No business fleet is
automatically migrated by releasing this version.

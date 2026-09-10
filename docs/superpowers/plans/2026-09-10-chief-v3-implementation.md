# Chief v3.0.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Chief v3.0.0 as a thin Goal Record → Next Action Loop → Acceptance Claim/Proof layer over the verified v2.0.2 capabilities.

**Architecture:** Keep schema 2 and existing v2 modules. Add one narrow `scripts/goal_loop.py` module that normalizes existing state plus fresh observations, gates one proposed action, and validates candidate-bound proof. Replace the large always-loaded Skill body with a compact router while preserving the v2 text as an on-demand compatibility reference.

**Tech Stack:** Python 3.12 standard library, `unittest`, Git CLI, Markdown Skill instructions, existing Chief schema-2 JSON state.

**Spec:** `V3_SPEC.md` and `V3_ACCEPTANCE.md`

## Global Constraints

- Base behavior is v2.0.2 at peeled commit `6b8b3a86867a30c43b3d013abf4169643d5bf7f2`; preserve the current documentation-only descendant.
- Keep contract schema `2` and `WORK_EXECUTION_V1`; add `GOAL_LOOP_V1` without rewriting v2 state.
- The only new persisted current-work field is `reference_sources`.
- Persist no absolute host path, Git observation, tool availability, or resource pressure.
- Add no long-lived Agent, database, message bus, workflow/DAG, general policy engine, evidence registry, or agent runtime.
- One implementation writer owns the repository. The existing Luna evaluator is the only read-only independent reviewer.
- Tests must exercise public behavior, real Git/file effects, and hand-derived expectations; no source-text assertions for behavioral requirements.
- Static/focused checks precede the full regression. Run no concurrent heavy workload.
- Do not modify the real Reservation v1.3 project or any remote/release target.
- No commit, push, tag, release, deployment, installation, fleet sync, or production action is authorized.
- Each task ends with a local candidate digest and check result instead of a commit.

## File Map

- `scripts/goal_loop.py`: one deep interface for Goal Record projection, one proposed-action verdict, and Acceptance Claim validation. It performs no host mutation.
- `scripts/work_execution.py`: expose the existing retained-proof validator and add explicit v3 adoption metadata; keep all v2 admission logic unchanged.
- `tests/test_goal_loop.py`: table-driven Goal/Action/Claim tests and the real Host/Reference integration replay.
- `tests/fixtures/host-reference-confusion-v3.json`: immutable historical roles, allowed effects, forbidden effects, expected observable outcome, and stop rule.
- `tests/test_work_execution.py`: public-proof seam and explicit-adoption compatibility regressions.
- `SKILL.md`: compact model-invoked v3 execution/router entrypoint.
- `references/chief-v2-compat.md`: byte-preserved former `SKILL.md`, loaded only for a v2 compatibility branch.
- `assets/chief-project-entry.md`: thin project pointer to the v3 Skill; no copied policy.
- `assets/project-template/.chief-of-staff/project.json`: `goal_loop_version` for new projects only.
- `chief-version.json`: version `3.0.0`, schema `2`, `WORK_EXECUTION_V1`, `GOAL_LOOP_V1`.
- `references/state-schema.md`: documents `reference_sources` and explicit v3 adoption metadata.
- `README.md`: concise v3 usage, compatibility, and non-capability boundary.
- `docs/releases/v3.0.0.md`: measured migration, Anti-Shit-Mountain ledger, verification, and limitations.

---

### Task 1: Freeze the execution workspace and baseline

**Files:**

- Preserve: `V3_SPEC.md`
- Preserve: `V3_ACCEPTANCE.md`
- Preserve: `docs/superpowers/plans/2026-09-10-chief-v3-implementation.md`
- Create later: every file in the File Map

**Interfaces:**

- Consumes: current clean tracked HEAD plus the two untracked approved specifications.
- Produces: one isolated local branch/worktree, baseline metrics, baseline test output, and no remote mutation.

- [ ] **Step 1: Create the isolated execution surface**

Invoke `superpowers:using-git-worktrees`. Start from
`fbadf78b67dfd42285e4a4a504978f3e5e00380f`, preserve the two specification
files byte-for-byte in the isolated surface, and name the local branch
`feat/chief-v3.0.0`. Do not create or update a remote branch.

- [ ] **Step 2: Prove the specifications survived isolation**

Run:

```bash
shasum -a 256 V3_SPEC.md V3_ACCEPTANCE.md
```

Expected:

```text
4ed63b6c20504af09b85de19e77ba3d445b72ab45141fd5818e1e3eb8b0343d9  V3_SPEC.md
b3877184d1872232a46a5b7e4c6f3213959a1deece4913350cb3498fd16c57a8  V3_ACCEPTANCE.md
```

- [ ] **Step 3: Capture measured v2 load and code baselines**

Run:

```bash
wc -l -w -c SKILL.md assets/chief-project-entry.md references/work-execution.md
find scripts tests -type f -name '*.py' -print0 | xargs -0 wc -l
git status --short --branch
```

Save the exact output in the work log for Task 6. Do not copy the measurements
into production state.

- [ ] **Step 4: Run the accepted baseline test entrypoints**

Run:

```bash
/Users/kai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -p test_work_execution.py
/Users/kai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -p test_project_paths.py
```

Expected: 23 work-execution tests pass; project-path tests pass with zero
failures. A dotted `tests.test_work_execution` invocation is not used because
two tests import sibling helpers through discovery-path names.

- [ ] **Step 5: Record the Task 1 candidate identity**

Run:

```bash
git diff --check
git status --short
```

Record the current HEAD and the SHA-256 of both specification files. Do not
stage or commit.

---

### Task 2: Add the Goal Record and one-step verdict seam

**Files:**

- Create: `scripts/goal_loop.py`
- Create: `tests/test_goal_loop.py`

**Interfaces:**

- Consumes: schema-2 `project`, `plan`, `work`, fresh `host_observation`, and retained authorization records supplied by the caller.
- Produces: `build_goal_record(project, plan, work_id, host_observation, authorizations) -> dict` and `next_action(goal_record, proposed_action, proof_state) -> dict`.

- [ ] **Step 1: Write the first failing Goal Record tests**

Create `tests/test_goal_loop.py` with a `GoalLoopTests` class. The first tests
use literal state and expect:

```python
record = goal_loop.build_goal_record(
    project={"approval_required": ["release", "external_message"]},
    plan={
        "goal_status": "confirmed",
        "final_goal": "Refactor local reservation behavior",
        "non_goals": ["visual change", "remote delivery"],
        "acceptance_criteria": [
            {"criterion_id": "reservation-path", "status": "pending", "evidence": []}
        ],
        "work_items": [{
            "work_id": "reservation-v13",
            "status": "queued",
            "input_sha256": "a" * 64,
            "write_surface": ["src/reservation.py"],
            "risk": {"level": "medium", "domains": []},
            "review": {"mode": "independent", "reviewer": "reviewer-luna"},
            "reference_sources": [{
                "repository": "https://github.com/zodorganization/zod-reservation.git",
                "revision": "8d1f9382033e70a35c9c08514caa298d6948d459",
                "purpose": "architecture",
                "access": "read_only",
            }],
        }],
    },
    work_id="reservation-v13",
    host_observation={
        "root_id": "project:reservation-v13",
        "path": "/disposable/local/reservation-v13",
        "revision": "b" * 40,
        "repository": "local://reservation-v13",
    },
    authorizations=[{
        "effect": "local_modify",
        "surfaces": ["src/reservation.py"],
        "decision_ref": "user:chief-v3-approved",
    }],
)
self.assertEqual(record["delivery_host"]["root_id"], "project:reservation-v13")
self.assertEqual(record["references"][0]["access"], "read_only")
self.assertEqual(record["permissions"]["local_modify"]["surfaces"], ["src/reservation.py"])
self.assertEqual(record["permissions"]["push"]["status"], "not_granted")
self.assertEqual(record["permissions"]["release"]["status"], "not_granted")
```

Add separate tests rejecting an unconfirmed goal, malformed/moving reference,
missing host identity, duplicate work ID, and authorization outside
`write_surface`.

- [ ] **Step 2: Run RED and verify the missing production seam**

Run:

```bash
/Users/kai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -p test_goal_loop.py
```

Expected: import or attribute failure naming `goal_loop` or
`build_goal_record`, not a fixture syntax error.

- [ ] **Step 3: Implement the minimal Goal Record projection**

Create `scripts/goal_loop.py` with this public surface:

```python
__all__ = ["GOAL_LOOP_VERSION", "GoalLoopError", "build_goal_record", "next_action"]

GOAL_LOOP_VERSION = "GOAL_LOOP_V1"
PROTECTED_EFFECTS = ("commit", "push", "release", "deploy", "production", "delete", "permission_expansion")

class GoalLoopError(ValueError):
    pass
```

Define `build_goal_record(project, plan, work_id, host_observation,
authorizations) -> dict` and `next_action(goal_record, proposed_action,
proof_state) -> dict` with those exact names and parameter orders.

Use plain JSON-serializable dictionaries. Validate full 40-hex reference
revisions, literal `read_only`, one matching work item, confirmed goal, complete
host identity, 64-hex input digest, authorization decision references, and
surface containment. Default every protected effect to `not_granted`; add no
permission store.

`next_action` returns one of these literal shapes:

```python
{"verdict": "STOP_ACCEPTED", "action": None, "reason": "all criteria have current proof"}
{"verdict": "EVIDENCE_REQUIRED", "action": None, "reason": "delivery host or reference identity is incomplete"}
{"verdict": "PERMISSION_REQUIRED", "action": None, "reason": "effect is not granted for the requested surface"}
{"verdict": "DECISION_REQUIRED", "action": None, "reason": "one material decision controls the result"}
{"verdict": "ACTION_READY", "action": proposed_action, "reason": "one admitted action closes the next proof gap"}
```

It accepts only one proposed action with `effect`, `surface`,
`expected_candidate_sha256`, and `closes_criterion_id`. It must reject lists,
graphs, follow-up actions, or a candidate mismatch.

- [ ] **Step 4: Run GREEN and the existing admission slice**

Run:

```bash
/Users/kai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -p test_goal_loop.py
/Users/kai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -p test_work_execution.py
```

Expected: every Goal Record/verdict test passes and all 23 existing work tests
remain green.

- [ ] **Step 5: Run the mutation check and record Task 2 evidence**

Temporarily invert the host/reference-role check and confirm the corresponding
test fails. Restore the implementation and rerun the focused suite. Record the
focused output, `git diff --check`, and the SHA-256 of `scripts/goal_loop.py`.

---

### Task 3: Bind Acceptance Claims to retained and observed proof

**Files:**

- Modify: `scripts/work_execution.py`
- Modify: `scripts/goal_loop.py`
- Modify: `tests/test_work_execution.py`
- Modify: `tests/test_goal_loop.py`

**Interfaces:**

- Consumes: existing `_proof(root, value)` semantics and one claim bound to the Goal Record candidate and host.
- Produces: `work_execution.validate_retained_proof(root, value) -> None` and `goal_loop.validate_acceptance(goal_record, claim, observation, proof_validator) -> dict`.

- [ ] **Step 1: Write failing proof-seam and claim tests**

Add a public-seam test in `tests/test_work_execution.py`:

```python
def test_public_retained_proof_validator_rejects_changed_bytes(self):
    retained = proof(self.root, "claim.txt", "observed user path passed")
    we.validate_retained_proof(self.root, retained)
    (self.root / "claim.txt").write_text("changed")
    with self.assertRaisesRegex(we.WorkExecutionError, "evidence bytes changed"):
        we.validate_retained_proof(self.root, retained)
```

Add table-driven claim tests that reject missing proof, wrong host, wrong
candidate, wrong criterion, stale observation, component-only proof where
`user_path_available` is true, unresolved findings, and an admission Boolean.
Add one literal valid claim with method `user_path`, result `passed`, matching
host/candidate, empty unresolved findings, and a retained proof object.

- [ ] **Step 2: Run RED**

Run both focused files. Expected: failures name
`validate_retained_proof` and `validate_acceptance`.

- [ ] **Step 3: Expose the existing proof seam without copying it**

Add to `scripts/work_execution.py`:

```python
def validate_retained_proof(root, value):
    """Validate existing repository-bound proof bytes for trusted callers."""
    _proof(_root(root), value)
```

Do not move or duplicate `_proof`, path validation, or hashing logic.

- [ ] **Step 4: Implement minimal Acceptance Claim validation**

Extend the public surface in `scripts/goal_loop.py` to:

```python
__all__ = [
    "GOAL_LOOP_VERSION",
    "GoalLoopError",
    "build_goal_record",
    "next_action",
    "validate_acceptance",
]
```

Define `validate_acceptance(goal_record, claim, observation,
proof_validator) -> dict` with that exact parameter order.

Require exact `criterion_id`, host `root_id`, candidate SHA-256, method, result,
nonempty proof list, `observed_effect: True`, matching post-action observation,
and an empty unresolved-findings list. Call the injected public proof validator
for every proof object. Return:

```python
{"status": "ACCEPTED", "criterion_id": claim["criterion_id"], "candidate_sha256": claim["candidate_sha256"]}
```

The validator raises `GoalLoopError` for every mismatch and never updates state
or performs a host action.

- [ ] **Step 5: Run GREEN and record Task 3 evidence**

Run both focused suites, then `git diff --check`. Record test counts and hashes
for both changed production modules. Do not stage or commit.

---

### Task 4: Execute the real Host/Reference Confusion replay

**Files:**

- Create: `tests/fixtures/host-reference-confusion-v3.json`
- Modify: `tests/test_goal_loop.py`

**Interfaces:**

- Consumes: Task 2/3 functions and real disposable Git repositories.
- Produces: one observed local change, unchanged reference/visual/remote state, one accepted criterion, then `STOP_ACCEPTED`.

- [ ] **Step 1: Add the immutable scenario fixture**

Create JSON with this exact semantic content:

```json
{
  "schema": "CHIEF_V3_HOST_REFERENCE_REPLAY_V1",
  "name": "重构预约v1.3 Host/Reference Confusion",
  "delivery_host": "caller_selected_local_project",
  "architecture_reference": {
    "repository": "https://github.com/zodorganization/zod-reservation.git",
    "revision": "8d1f9382033e70a35c9c08514caa298d6948d459",
    "purpose": "architecture",
    "access": "read_only"
  },
  "allowed_effects": {"local_modify": ["src/reservation.py"], "reference_read": ["architecture"]},
  "forbidden_effects": ["visual_modify", "commit", "push", "release", "deploy", "production"],
  "protected_visual": "assets/current-visual.bin",
  "criterion_id": "reservation-user-path",
  "stop_after_acceptance": true
}
```

- [ ] **Step 2: Write the failing end-to-end replay**

Use `tempfile.TemporaryDirectory` and real `git init`, `git add`, `git commit`,
`git rev-parse`, `git show`, `git diff --name-only`, and `git show-ref` calls.
Configure disposable commit identity with command-local `-c user.name=ChiefV3`
and `-c user.email=chief-v3@example.invalid`; do not modify global Git config.

The host contains `src/reservation.py`, an executable user-path check, and
`assets/current-visual.bin`. The reference contains an architecture note at a
fixed commit. The test reads that note with `git show <sha>:architecture.txt`,
uses it to perform one real edit to the host source, runs the user-path command,
constructs proof from independently hashed output, validates the claim, and
calls `next_action` again.

Expected final assertions are literal:

```python
self.assertEqual(changed_paths, ["src/reservation.py"])
self.assertEqual(reference_head_before, reference_head_after)
self.assertEqual(reference_tree_before, reference_tree_after)
self.assertEqual(visual_sha_before, visual_sha_after)
self.assertEqual(remote_refs_before, remote_refs_after)
self.assertEqual(host_head_before, host_head_after)
self.assertEqual(effect_audit, ["reference_read", "local_modify", "user_path_check"])
self.assertEqual(modifying_action_count, 1)
self.assertEqual(final_decision["verdict"], "STOP_ACCEPTED")
```

- [ ] **Step 3: Verify RED catches the absent real chain**

Run only the replay test. Expected: it fails because the Goal Loop cannot yet
bind the post-action observation to the accepted proof or stop state. A syntax,
Git identity, or fixture-path error is not an acceptable RED signal.

- [ ] **Step 4: Add only the integration glue required by the replay**

Keep real Git/file commands in test utilities because Chief's production module
does not own host execution. Modify production code only if the replay exposes
a missing host/reference/candidate invariant. Do not add a runner, adapter
framework, command dispatcher, or reference clone manager.

- [ ] **Step 5: Run GREEN and all falsification cases**

Run the full `test_goal_loop.py`. Confirm every A1 mutation rejects before an
effect or invalidates the claim. Temporarily remove the production
Host/Reference guard, observe a replay failure, restore it, and rerun green.
Record the exact test count, fixture hash, changed-path observation, and final
`STOP_ACCEPTED` verdict.

---

### Task 5: Make v3 the thin active Skill while preserving v2

**Files:**

- Replace: `SKILL.md`
- Create: `references/chief-v2-compat.md`
- Modify: `assets/chief-project-entry.md`
- Modify: `assets/project-template/.chief-of-staff/project.json`
- Modify: `chief-version.json`
- Modify: `scripts/work_execution.py`
- Modify: `tests/test_work_execution.py`
- Modify: `tests/test_init_project.py`
- Modify: `references/state-schema.md`

**Interfaces:**

- Consumes: current v2 Skill bytes, Task 2/3 Goal Loop, explicit project sync/adoption.
- Produces: a compact v3 router, byte-preserved v2 compatibility source, and explicit `GOAL_LOOP_V1` adoption.

- [ ] **Step 1: Freeze and test the pre-edit Skill behavior**

Record `shasum -a 256 SKILL.md`. Preserve the current file byte-for-byte as
`references/chief-v2-compat.md`. Reuse the existing Luna baseline transcript as
the RED pressure result: it chose the correct host only by inference and found
no explicit dual-source field, while warning that `--check-work` can be mistaken
for execution.

- [ ] **Step 2: Write failing metadata and explicit-adoption tests**

Add tests proving:

```python
self.assertEqual(version["version"], "3.0.0")
self.assertEqual(version["schema_version"], 2)
self.assertEqual(version["work_execution_version"], "WORK_EXECUTION_V1")
self.assertEqual(version["goal_loop_version"], "GOAL_LOOP_V1")
```

For a fresh project, require `project.json.goal_loop_version ==
"GOAL_LOOP_V1"`. For a valid v2 project, prove a preview writes nothing and an
explicit sync/adoption adds the field while preserving unknown keys, history,
approvals, and failures.

Run RED and confirm failures are the missing version/adoption values.

- [ ] **Step 3: Replace the always-loaded entrypoint**

The new `SKILL.md` keeps the existing `name`, model-invoked policy, and a concise
description. Its body contains only:

1. establish the caller-selected delivery host and fixed read-only references;
2. project one Goal Record from existing state plus fresh observations;
3. run one Next Action iteration;
4. treat the returned action as intent until a real host effect is observed;
5. bind Acceptance Claims to proof and prefer the real user path;
6. load conditional references for build, Testing, visual, product discovery,
   migration/task governance, preferences, or v2 compatibility;
7. stop at `STOP_ACCEPTED` or an exact authority/identity/safety gate.

It states local edit, commit, push, release, and delivery as separate effects.
It links `V3_SPEC.md`, `V3_ACCEPTANCE.md`, `scripts/goal_loop.py`, and every
action-triggered existing reference. It does not restate those references.

Update `assets/chief-project-entry.md` so current work first loads `SKILL.md`;
`references/work-execution.md` loads only for v2 admission, budget, retry,
resource, build, or compatibility questions.

- [ ] **Step 4: Add explicit version and adoption metadata**

Set `chief-version.json` to:

```json
{
  "version": "3.0.0",
  "schema_version": 2,
  "work_execution_version": "WORK_EXECUTION_V1",
  "goal_loop_version": "GOAL_LOOP_V1"
}
```

Add `goal_loop_version` to the fresh project template. In
`work_execution.sync_project`, copy it from `chief-version.json` only during an
explicit apply; preview remains byte-for-byte read-only. Do not make source
checkout discovery an adoption event.

Document `reference_sources` and the new version field in
`references/state-schema.md` without duplicating the full v3 spec.

- [ ] **Step 5: Run GREEN and skill checks**

Run focused Goal Loop, work-execution, initialization, sync, and activation
tests. Validate the Skill with the bundled `quick_validate.py`; if its runtime
still lacks PyYAML, record the infrastructure error and run the repository's
frontmatter parser plus placeholder scan without labeling that fallback as
quick-validator PASS.

Measure `SKILL.md` and `assets/chief-project-entry.md` lines, words, and bytes.
Confirm the v2 compatibility file hash equals the pre-edit `SKILL.md` hash.

---

### Task 6: Document migration evidence and host limitations

**Files:**

- Modify: `README.md`
- Create: `docs/releases/v3.0.0.md`

**Interfaces:**

- Consumes: exact baseline metrics, exact candidate metrics, replay output, test output, and Git diff.
- Produces: measured v2→v3 migration report and concise public usage facts.

- [ ] **Step 1: Write the migration report from measured evidence**

Include these sections with actual values:

- candidate identity and uncommitted-diff hash;
- always-loaded line/word/byte comparison;
- action-triggered reference list;
- Host/Reference replay: durable Agent/handoff count, authorization prompts,
  waits, action count, changed paths, and stop verdict;
- production/test/documentation additions and deletions;
- retained, replaced, and retired modules;
- Anti-Shit-Mountain ledger;
- focused and full-regression results;
- host abilities exercised and unresolved limitations;
- adoption and rollback boundaries.

The ledger must contain exactly the observed additions. Expected initial rows:

```markdown
| Item | Regression solved | Complexity removed | Deletion/persistence test |
| --- | --- | --- | --- |
| `scripts/goal_loop.py` | Host/reference role confusion and false completion | Reconciliation leaves Skill/callers | Deleting it redistributes the same guards across callers |
| `reference_sources` | Fixed architecture input mistaken for delivery source | One role-bound reference list | Repository/revision/purpose are not derivable from the local host |
| `validate_retained_proof` public seam | Claim validation would duplicate v2 hash/path rules | Reuses one existing validator | Wrapper delegates to the existing implementation and has a real second caller |
```

If implementation adds another row, it must pass `V3_ACCEPTANCE.md` A6 or be
removed before review.

- [ ] **Step 2: Update README without copying the specification**

Add a short v3 section covering the core loop, exact install/adoption version,
v2 compatibility pointer, real-user-path proof, and the statement that policy
results do not create host capabilities. Preserve the current README artwork,
credits, bilingual facts, and existing v2 release history.

- [ ] **Step 3: Measure the exact diff**

Run:

```bash
git diff --numstat
git diff --stat
wc -l -w -c SKILL.md assets/chief-project-entry.md references/chief-v2-compat.md
```

Classify additions/deletions into production, tests, and documentation using
the actual file list. Do not count the byte-preserved compatibility move as new
behavior.

- [ ] **Step 4: Compute an uncommitted candidate digest**

Because commit is not authorized, hash a deterministic patch plus untracked
file manifest. Record the exact recipe and result in the release report. The
recipe must include every changed or new file and exclude `.git`, caches, and
temporary test directories.

- [ ] **Step 5: Run documentation consistency checks**

Verify every version, hash, command, module-retirement statement, and limitation
against current files and command output. Run `git diff --check` and a scan for
unfinished placeholders. Do not claim the release exists.

---

### Task 7: Run final regression and independent review

**Files:**

- Review only: every changed file
- Modify only if a concrete review finding requires a focused repair cycle

**Interfaces:**

- Consumes: exact uncommitted candidate digest, `V3_SPEC.md`, `V3_ACCEPTANCE.md`, and all prior evidence.
- Produces: fresh verification output plus separate Standards and Spec findings from the existing read-only Luna evaluator.

- [ ] **Step 1: Run static and focused checks**

Run Python compilation for every changed script, Goal Loop/replay tests, and
all affected v2 suites: work execution, project paths, Testing control, Testing
evidence, build execution, initialization, sync, preferences, and activation.
Any failure blocks the full suite until repaired through a new red-green cycle.

- [ ] **Step 2: Run the complete Chief regression**

Run:

```bash
/Users/kai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests
```

Read the full output and record total run, pass, skip, error, and failure counts.
Do not convert an infrastructure error into a product failure or a PASS.

- [ ] **Step 3: Recompute the exact candidate digest after verification**

If any file changed after Task 6, recompute the patch/manifest digest, update the
release report, and rerun every check whose input changed. Bind all final claims
to the recomputed candidate.

- [ ] **Step 4: Request one independent dual-axis review**

Reuse `/root/v3_baseline_replay` with a fresh follow-up. It remains read-only,
cannot delegate, and receives only the exact candidate digest, repository path,
`V3_SPEC.md`, `V3_ACCEPTANCE.md`, and the command to inspect the current diff.
Ask for two separate reports:

- Standards: repository rules, code smells, deep-module/deletion test, test
  quality, and protected boundaries.
- Spec: every V3 acceptance criterion, Host/Reference replay, migration metrics,
  and host limitations.

Critical or important findings require a focused writer repair followed by the
same reviewer's exact-candidate recheck. Use at most the remaining three-cycle
budget and never weaken an acceptance criterion.

- [ ] **Step 5: Stop and report the local candidate**

Run final `git status --short`, `git diff --check`, focused tests, and the full
suite after the last changed byte. Report actual changes, exact digest, tests,
independent findings, and limitations. State explicitly that the candidate is
local/uncommitted and that no push, tag, release, installation, migration, or
business-project change occurred. Stop; request separate authority before any
commit, push, or release.

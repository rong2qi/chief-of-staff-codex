# Chief v3.0.0 Acceptance

Status: normative acceptance contract; implementation not started.

## Acceptance rule

Chief v3.0.0 is accepted only when the exact candidate satisfies every required
criterion below with fresh evidence. Passing component tests or returning a
policy decision cannot substitute for observing the corresponding host effect.

No test in this contract authorizes modification of the real Reservation v1.3
project, a remote repository, a release target, or production. Behavioral
replays use disposable local repositories while preserving the historical
identities and permission boundaries that caused the regression.

## A1 — Host/Reference Confusion replay

### Historical contract

- Delivery host: the caller-selected local project named `重构预约v1.3`.
- Architecture reference: remote `zodorganization/zod-reservation` fixed at
  `8d1f9382033e70a35c9c08514caa298d6948d459` for the replay. It is readable and
  read-only; it is not the delivery host.
- Current delivery-host visual state must remain byte-for-byte unchanged.
- Local implementation changes are in scope only on named non-visual surfaces.
- Local commit, remote push, release, deployment, and production changes are
  not authorized.
- The loop stops after the requested local change and its proof are complete.

This current contract overrides any older record that described the fixed
remote commit as a delivery source. The replay tests the user's corrected
Host/Reference roles, not the historical misclassification.

The repository and commit identity above comes from retained project history.
Anonymous GitHub access did not confirm that the private or removed object is
currently available. The disposable replay therefore proves real fixed-commit
reading and role isolation, not present access to the business remote. Before
real project adoption, the executing host must independently revalidate its
authorized read access to that exact reference and report any limitation.

### Disposable fixture

The automated replay creates:

1. a temporary Git repository representing local `重构预约v1.3`;
2. a separate temporary Git repository containing a fixed architecture commit;
3. a local host source file with a behavior that needs the bounded refactor;
4. a host visual asset whose initial SHA-256 is recorded;
5. a remote ref snapshot and release-artifact inventory;
6. an action counter and command/effect audit.

The fixture may reproduce the architecture fact from the fixed reference, but
the actual edit must occur through the local host path selected by the caller.

### Required execution

The replay must exercise a real end-to-end slice:

1. resolve the delivery host from the caller-selected temporary project;
2. resolve its portable identity and actual Git state;
3. read architecture material from the separate fixed commit with a real Git
   read operation;
4. select one local modifying action;
5. revalidate the effect-scoped authorization immediately before the write;
6. perform a real filesystem edit on the allowed local host source file;
7. run a user-observable acceptance command against the changed host;
8. collect independent hashes and Git observations;
9. issue the Acceptance Claim only after those observations pass;
10. run the loop again and receive `STOP_ACCEPTED` without another write.

### Required proof

The replay passes only if all observations are true:

- the local host source has the expected observable behavior;
- the local host Git diff contains only the authorized non-visual surface;
- the reference repository's fixed commit and worktree bytes are unchanged;
- the reference was actually read at the fixed commit;
- the visual asset SHA-256 is unchanged;
- the remote ref snapshot is unchanged;
- no commit was created;
- no push, tag, release, deploy, or production command was invoked;
- no release artifact was created;
- exactly one modifying action occurred;
- the second loop iteration stopped because every in-scope criterion had proof;
- no durable Agent, Chief, task, automation, database, queue, or workflow object
  was created.

The proof must report the exact temporary host path, host commit before and
after, reference commit, changed paths, visual hash before and after, remote refs
before and after, invoked effect classes, acceptance command and exit status,
and final loop verdict.

### Falsification checks

Each mutation below must fail before any modifying action, or invalidate the
Acceptance Claim after observation:

- swap the delivery host and reference identities;
- omit the reference commit or use a moving branch name;
- grant local write but request reference write;
- grant source write but request visual modification;
- treat local-edit permission as commit, push, or release permission;
- change the host candidate after precheck but before write;
- change the reference commit after selection;
- return a successful policy/admission value without executing the host edit;
- pass a component-only test while the user-observable behavior remains wrong;
- modify the correct host but also change the visual asset;
- satisfy acceptance and then schedule or execute an additional action.

At least one test must prove that the replay goes red when the production
Host/Reference guard is removed or inverted, then green when restored.

## A2 — Goal Record

The normalized Goal Record must be constructible from existing project state
plus fresh observations without creating a second state store.

Acceptance evidence must show:

- goal, non-goals, criteria, current work, write surfaces, references,
  effect-scoped authorization, candidate identity, risk, proof gaps, and stop
  conditions are present;
- current absolute path, Git state, tool availability, and resource pressure
  are freshly observed rather than cached as durable truth;
- the only new persisted work-item field is `reference_sources`, whose fixed
  identity, purpose, and read-only role cannot be safely inferred from the
  delivery environment;
- effect-scoped authorization is projected from existing write surfaces,
  protected actions, retained decisions, and approvals rather than copied into
  a second permission store;
- existing unknown fields, approvals, failures, and history survive read/write
  compatibility checks.

## A3 — Next Action Loop

Table-driven tests must cover every terminal shape:

| State | Required verdict |
| --- | --- |
| All in-scope criteria have current proof | `STOP_ACCEPTED` |
| Delivery host or reference role is ambiguous | evidence gate; no effect |
| Requested effect lacks surface authorization | permission gate; no effect |
| One material user decision controls the result | decision gate; no effect |
| Proof gap has one admitted safe action | exactly one action intent |
| Host action has not been observed | not accepted |
| Host action failed | exact failure; no false proof |
| Candidate drifted before effect | stale-candidate gate; no effect |

The loop must not model arbitrary graphs, schedule background work, or create a
general workflow language. Tests assert one-step observable decisions and
effects, not internal class or function names.

## A4 — Acceptance Claim/Proof

Acceptance validation must reject:

- missing, empty, stale, malformed, or wrong-candidate proof;
- a self-authored value presented as independent review;
- an admission/check function's return value presented as execution evidence;
- a build result presented as install, release, or delivery evidence;
- a component test presented as the real user-path result when that path is
  available;
- proof from the reference repository presented as delivery-host proof;
- proof covering only part of the in-scope criteria.

It must accept a claim only when the exact host, candidate, criterion, method,
result, and proof agree and no applicable unresolved finding remains.

## A5 — Skill loading and review routing

Behavioral forward tests must show:

- a simple local bounded change loads the core loop and only the reference
  needed for that action;
- build rules load only for build/package work;
- visual rules load only when visual output may change;
- product discovery loads only for a genuinely new product boundary or
  material unresolved product change;
- Testing/review is triggered by risk, changed inputs, dependency impact, or
  concrete uncertainty, not merely by a new version, file, phase, or candidate;
- the Host/Reference replay creates no durable handoff and uses at most the one
  independent read-only verification required by the implementation contract.

Forward tests must compare Standards findings against repository rules and Spec
findings against `V3_SPEC.md`; one axis cannot cancel the other.

## A6 — Anti-Shit-Mountain

The implementation diff must include a short ledger with one row per new
abstraction or persistent field:

| Item | Required justification |
| --- | --- |
| New abstraction | reproduced regression, removed caller complexity, deletion test |
| New persistent field | why fresh environment observation cannot supply it |

Acceptance fails if the ledger identifies a speculative abstraction,
pass-through module, duplicate source of truth, or persistence of cheaply
observable machine state. It also fails if the candidate adds a durable Agent,
database, message bus, workflow/DAG, general policy engine, evidence registry,
or agent runtime.

## A7 — Compatibility and regression

Required checks for the exact candidate are:

1. Host/Reference replay and its falsification tests;
2. focused Goal/Next-Action/Acceptance tests;
3. existing work-execution, project-path, Testing-control, Testing-evidence,
   build-execution, initialization, sync, and preference tests affected by the
   diff;
4. Skill frontmatter/placeholder validation;
5. Python compilation for changed scripts;
6. `git diff --check`;
7. the complete Chief regression suite after focused checks pass.

The recorded baseline for the existing work-execution slice is 23 passing tests
with the repository's discovery invocation. A direct dotted-module invocation
is not the accepted command because two tests import sibling test helpers by
discovery-path name.

No existing module may be deleted merely because its tests pass through a new
wrapper. Retirement requires proof that the active v3 path replaced every
applicable caller and protected behavior.

## A8 — Migration report

`docs/releases/v3.0.0.md` must report measured before/after values for:

- always-loaded `SKILL.md` and managed project-entry lines, words, and bytes;
- which references are now action-triggered;
- durable Agent/handoff count in the Host/Reference replay;
- authorization prompts and waiting states in that replay;
- production, test, and documentation lines added and deleted;
- retained, replaced, and retired modules;
- focused and full-regression command results;
- candidate commit or, when commit remains unauthorized, the exact tree/diff
  hash used for verification;
- actual host operations exercised by acceptance;
- host limitations that code and policy cannot supply.

At minimum, limitations must state that Chief cannot create a host capability by
returning a policy result, cannot prove unobserved UI/native events, cannot push
or release without explicit authority and an available host tool, and cannot
turn a disposable replay into proof that the real business project was changed.

## A9 — Stop and delivery boundary

After all required checks pass, implementation stops and reports the candidate,
evidence, and unresolved limitations. It does not perform speculative cleanup,
fleet migration, installation, commit, push, tag creation, release, deployment,
or business-project modification.

The candidate remains local and uncommitted unless the user separately
authorizes a commit. Push and release always require their own later approval.

# Chief v3.0.0 Specification

Status: design approved for specification; implementation not started.

## Goal

Chief v3.0.0 is a goal-driven thin execution layer over the verified Chief
v2.0.2 capabilities. It keeps one current Goal Record, selects one safe Next
Action from fresh evidence, and accepts completion only through an Acceptance
Claim bound to observable Proof.

The migration reduces always-loaded coordination rules without replacing
working v2 modules merely to make the version look new.

## Baseline and reference

- Implementation base: `v2.0.2`, peeled commit
  `6b8b3a86867a30c43b3d013abf4169643d5bf7f2`.
- Current repository HEAD at specification time:
  `fbadf78b67dfd42285e4a4a504978f3e5e00380f`; the post-v2.0.2 change is
  documentation and README artwork, not a replacement execution engine.
- Important design reference: `vinvcn/mattpocock-skills-zh-CN`, fixed commit
  `9fe7e7a3bb352851b986725bab1c7cfb17610a97`.
- Adopted ideas from that reference: small composable skills, feedback loops
  that exercise real behavior, vertical slices, deep modules, explicit seams,
  and separate Standards versus Spec review.
- Reference material informs design. It is not an execution host, dependency,
  installation authorization, or source of permission.

## Required outcomes

1. A Chief invocation can identify the delivery host separately from every
   read-only reference source before selecting a modifying action.
2. One loop iteration returns exactly one of: perform one admitted action,
   gather evidence needed to choose, request one material decision, or stop.
3. A successful policy/admission result is never reported as host execution or
   acceptance proof.
4. Skills and detailed governance references load only when the current action
   triggers them.
5. Independent review is selected from risk and evidence, not from file count,
   version number, phase name, or the mere existence of a candidate.
6. Observable user paths outrank component-only green signals.
7. When every in-scope acceptance criterion has current proof, Chief stops.

## Non-goals

v3.0.0 does not add a long-lived Agent, database, message bus, workflow/DAG,
general policy engine, evidence registry, or agent runtime. It does not rewrite
all v2 modules, migrate every existing Chief project automatically, install the
reference repository, modify a business repository during framework testing,
or authorize commit, push, release, deployment, production changes, payment,
external messages, deletion, or permission expansion.

## Core model

### Goal Record

The Goal Record is a normalized view over existing state, not a new state file.
It draws from `project.json`, `project-plan.json`, the current work item,
project overrides, and fresh host observations.

It contains only facts needed to choose or accept the next action:

- confirmed goal and explicit non-goals;
- in-scope deliverables and criterion IDs;
- current delivery-host identity;
- fixed read-only reference identities and their purposes;
- write surfaces and effect-scoped authorization;
- current candidate/input identity;
- applicable risk and required review route;
- current proof or proof gaps;
- stop conditions.

The current absolute project path, current Git state, available host tools, and
resource pressure are observed at action time because they are cheaply
available and can drift. User intent, fixed reference revisions, granted or
withheld effects, acceptance criteria, and retained decisions may be persisted
because they cannot be safely reconstructed from the environment.

Existing v2 state remains authoritative. v3 adds exactly one optional persisted
field to the existing current-work record: `reference_sources`. Each entry binds
a repository or retained source, full revision, purpose, and read-only access.
This identity and purpose cannot be recovered safely from the delivery host.
The field must not duplicate the existing goal, criteria, delivery `source`,
history, Testing evidence, or approval queue under new names.

Effect-scoped authorization is normalized from the existing work item's
`write_surface`, the project's protected-action list, retained user decisions,
and approval queue. v3 does not create a second permission store.

### Delivery host and references

The delivery host is the project whose observable state the user asked to
change. Resolve it from the caller-selected project, current repository, and
existing portable `root_id` rules. A repository mentioned in a brief, incident,
log, issue, or reference packet does not replace the delivery host.

Each reference has an exact identity, preferably repository plus full commit,
an explicit purpose, and read-only access. Reading and comparing a reference is
allowed only within the already authorized research/input boundary. A reference
never inherits the host's write surface or remote permissions.

Before a modifying action, fail closed if the delivery host or a reference role
is ambiguous, the host has drifted from the observed candidate, or a requested
effect is not authorized for that surface.

### Effect-scoped authorization

Authorization is recorded by effect and surface. The minimum distinctions are:

- read local project state;
- read a fixed external reference;
- modify named local project surfaces;
- modify visual output;
- create a local commit;
- push or otherwise mutate a remote;
- build or package an artifact;
- release, deploy, or change production;
- delete data or expand permissions.

A grant for one effect does not imply another. In particular, local editing does
not grant commit; commit does not grant push; a successful build or test does
not grant release; access to a reference does not grant writing to it.

### Next Action Loop

Each iteration follows this interface:

1. Observe the actual host, candidate, references, permissions, and proof.
2. Reconcile them with the Goal Record and applicable project overrides.
3. If acceptance already has current proof, return `STOP_ACCEPTED`.
4. If identity, authority, ownership, safety, or a material decision is missing,
   return the corresponding evidence/action gate without modifying anything.
5. Load only the skill or v2 reference triggered by the selected action.
6. Select one smallest action that can close a proof gap or remove a blocker.
7. Revalidate immediately before the effect, then let the actual host perform
   the action through its real tool or command.
8. Observe the resulting state. Record proof or an exact failure, then begin a
   new iteration.

The loop is not a scheduler. It creates no background work and promises no host
capability. A returned action is an intent until the host effect is observed.

### Acceptance Claim and Proof

An Acceptance Claim names one criterion, exact candidate/input identity, host,
observable result, verification method, and proof. Proof must be current and
independently derived from the result being checked.

Examples of valid proof include a real user-path test result, exact artifact
hash plus required validators, observed file/Git state, or an independent review
receipt bound to the same candidate. A function returning `True`, an admitted
work item, a transport acknowledgement, a component-only test, or a prose report
is not proof of a host effect it did not observe.

Completion requires every in-scope criterion to have valid current proof, no
unresolved applicable finding, and no claimed effect outside authorization.
Phase completion, code completion, build success, review, commit, push, release,
and delivery remain distinct states.

## Progressive disclosure

The v3 `SKILL.md` will contain only the core loop, authority invariants, stop
rule, and short trigger pointers. Detailed v2 capabilities stay in their
existing modules or a preserved compatibility reference and load only when the
current action requires them, including:

- work admission, budgets, retries, and state compatibility;
- Testing evidence and risk-based control;
- product discovery for genuinely new or materially changed products;
- visual selection;
- build/package verification;
- task, automation, pin, migration, and context-handoff governance;
- optional operator preferences.

Pointers must state the observable trigger for loading their target. The v3
entrypoint must not duplicate the target's rules.

## Compatibility and migration

- Preserve contract schema 2 unless implementation evidence proves a schema
  change is unavoidable.
- Keep existing v2 scripts and state readable.
- Preserve unknown extension fields, approvals, failures, task identities,
  candidate bindings, and user overrides.
- Existing projects do not adopt v3 merely because the source checkout changes.
- A v2 module is retired only after the v3 path is the active caller, equivalent
  protected behavior is covered, and real-path tests prove replacement.
- No automatic fleet sync, installation, project migration, commit, push, tag,
  or release occurs in this work.

## Anti-Shit-Mountain gate

Every new abstraction must name the reproduced regression it prevents and the
callers whose complexity it removes. Every new persistent field must state why
the value cannot be obtained cheaply and safely from the current environment.
If either case cannot be shown, keep the logic local or omit it.

The implementation review rejects speculative adapters, pass-through modules,
duplicate state, duplicated instructions, generic orchestration primitives,
and tests that assert wording or implementation structure instead of behavior.

## Planned change surfaces

The implementation plan may change only these classes of files unless later
evidence requires a separately approved scope change:

- `SKILL.md` and a preserved v2 compatibility reference;
- `chief-version.json`, existing release metadata, and README version facts;
- one narrow deep module at `scripts/goal_loop.py` for Goal Record projection,
  one-step decisions, and Acceptance Claim validation;
- focused tests and the Host/Reference replay fixture;
- `docs/releases/v3.0.0.md` migration and limitation report;
- existing project template fields only when a field passes the persistence
  gate above.

`scripts/goal_loop.py` is justified by the reproduced Host/Reference confusion:
it gives the Skill and acceptance replay one interface for facts currently
scattered across project state, Git observations, and reference inputs. Its
public surface is limited to Goal Record projection, one-step evaluation, and
claim validation. Actual host effects remain outside the module. The deletion
test is that removing it would re-spread host/reference reconciliation and
false-completion checks across the Skill, replay, and future host callers.

`work_execution.py` remains the v2 admission and compatibility module. The new
module may call its established validation seams but must not copy its budget,
retry, discovery, resource, build, or Testing logic.

## Required migration report

The v3 release report compares v2.0.2 and the exact v3 candidate for:

- always-loaded rule lines, words, and bytes;
- action-triggered reference load;
- durable Agent creation and handoff count in the acceptance replay;
- repeated authorization requests and waiting states in that replay;
- production/test/documentation additions and deletions;
- retained versus retired v2 modules;
- targeted and full-regression results;
- host abilities actually exercised and host limitations still unresolved.

Metrics are measurements, not success by themselves. The acceptance file
defines the behavioral gate.

# Opt-in continuous execution

Every retry consumer reloads project progress/measurement observations through
the held no-follow project directory, and approval/review/diagnosis observations
through one held external coordinator directory. Receipt
hashes establish retained-byte integrity only: authority remains the existing
independent approval/Testing observation and exact plan/registry binding. A
fresh ID for the same criterion transition, absent measurement, or replayed
receipt does not produce another cycle.

An approved `CHIEF_EXECUTION_PACKAGE_V1` is an exact, local work contract. It
binds one `work_id`, project ID/root ID/branch, sole writer, goal, local
endpoint, finite local permissions, finite resource limits, acceptance items,
stop conditions, and an approved queue record. It belongs in the existing
`project-plan.json` as `execution_packages`; the matching task records its
`execution_work_id` and `execution_package_id`. Missing fields mean the legacy
three-cycle/one-shot contract remains in force.

The approval is not a Boolean: its queue record and package share an exact
receipt SHA-256 and `native://` evidence reference. The host supplies the exact
external native root and nine-field intake separately; a writer-side Boolean,
copied observation or self-declared reviewer does not supply authority. The
consumer compares held directory ancestry (including OS aliases), reads the
one-link native JSON, recomputes its hash and checks approval/package identity.
Progress and resource measurements use project-relative `repo://` observations.
A progress observation
also binds work, package, candidate, criterion and a real before/after delta;
an arbitrary log text or a changed ID pointing to the same bytes is not proof.
The package's `candidate_sha256` is the fixed approval baseline, not the output
of every future round. Each original native review additionally binds its exact
`candidate_id`, `reviewed_artifact.sha256`, `outcome_ref` and `outcome_sha256`.
The outcome must identify that artifact; historical rounds revalidate the
original review, outcome, measurement and retained artifact binding. A fresh
artifact hash alone does not create a new criterion transition.

Only distinct retained evidence of an acceptance gain, removed blocker, or
reproducibly established new cause counts as progress. New IDs, repeated logs,
and copied evidence do not. A package may exceed three repair cycles only while
each cycle has such evidence and stays below its finite resource and progress
limits. Two stagnant rounds request one independent diagnosis; continuation
needs that diagnosis's reviewer, evidence reference, and a new evidenced path.
The diagnosis binds exactly the currently stagnant round pair, package, work,
candidate and a pre-registered independent reviewer; it cannot be reused for a
later pair. A nonempty route label is insufficient: the diagnosis includes
`new_path_evidence_ref` and `new_path_evidence_sha256` for a retained native
reproduction with the exact pair, reviewer, package and before/after result.
The next original review must carry the exact `diagnosis_used` receipt and
new-path references. Subsequent rounds revalidate that history. No new round,
resource counter or dispatch is created by attaching a diagnosis.

When an explicitly enabled autonomy policy permits a new phase, its counter
starts at zero only after the transition retains the prior phase and failure
evidence, binds a distinct plan/candidate to an existing approved queue record
and sole active writer, and declares finite stop/resource bounds no larger than
the approved package. The transition is not a permission reset: pauses,
denials, protected actions, safety conclusions, and the complete old history
remain retained. A phase-name change alone is rejected.

The local reconciler returns intents only. It keeps running, testing queue,
input, permission, quota, technical-blocked, and local-delivered states
distinct; it never reopens paused/archived/wrong-owner work. Returns bind the
current work/package and are dispatched once by stable return ID. Empty or
timeout observations are gaps, never blind replay. An older completed work ID
cannot close a newer ID.

`delivery_ledger.py continuous-reconcile` validates the original return,
reviewed ledger report, registered writer, exact native current-task observation
and independently supplied HEAD before preparing an action. Its four native
return consumers are:

| Return | Exact waiting state | Required release evidence |
| --- | --- | --- |
| `approval` | `awaiting_permission` | The same already approved package/approval/hash; no new permission inferred |
| `resource_recovered` | `quota_limited` | Capacity available, same cumulative units/unit, no paid capacity or budget reset |
| `recovery` | `technical_blocked` | Exact native recovery receipt |
| `test_pass` | `testing_queue` | Original Testing receipt and approved testing policy |

The first accepted return emits `DISPATCH_RETURNED_WORK` and records a pending
intent. It does not itself call a tool. After restart, a pending intent emits
`OBSERVE_RETURN_DISPATCH`, never another send. Only an exact retained native
accepted-dispatch receipt marks it dispatched; even a no-argument replay
revalidates those receipt bytes. A transport success is not a task's success.
`awaiting_input`, paused/archived targets and an exhausted resource allowance
remain held. Permission to resume one action does not loosen another action's
restrictions.

Delegated testing needs a pre-registered independent reviewer, the privately
operator-provisioned Testing reviewer's exact delegation ID, low/medium risk,
candidate SHA-256, and scope. High risk, disputed, sensitive/production, and
this global upgrade stay with that reviewer. Its identity is resolved only from
the independently SHA-256-pinned host-private authority configuration described
in `agent-os-v1.md`; no candidate, receipt, project, or package may supply it.
A local commit is permitted only when the package lists
it; remote, production, payment, external-send, and permission-expansion
actions are never implied.

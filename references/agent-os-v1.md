# Agent OS V1 integration

## When this applies

Fresh Chief projects record `agent_os_mode: required` and
`agent_os_manifest: .agent-os/manifest.json` in `.chief-of-staff/project.json`.
Their `AGENTS.md` is the Codex/Chief adapter, while `CLAUDE.md` is a separate
thin adapter. Both point to the shared `.agent-os/CORE.md`; only the Codex
adapter retains Chief task, pin, automation, and governance authority.

Projects whose state omits both Agent OS fields are legacy. Normal initializer
reruns and `--check` preserve that state and do not create or verify an Agent
OS contract. Promote a legacy Chief project only with explicit intent:

```bash
python3 scripts/init_project.py --target <project-root> --migrate-agent-os
```

Migration preserves the prior Chief instructions inside the Codex adapter,
adds the required-mode state, and then validates the resulting contract. Do
not use it to repair an incomplete or conflicting contract; resolve that
condition explicitly first.

For an explicitly authorized custom legacy `AGENTS.md`, pass all three of
`agent_os.py migrate`'s `--legacy-agents-gate`,
`--expected-legacy-agents-gate-sha256`, and `--legacy-trust-root` inputs. The
gate must be an external, one-link regular file below the external trust root;
it binds the exact pre-migration project JSON and AGENTS bytes, project
identity, fixed Testing Chief PASS, INFRA_CONFIG and SECURITY_PRIVACY lanes,
required mode, and a non-empty operator approval ID. The command never creates
or refreshes that evidence. It records only the gate ID and integrity hashes in
the isolated contract transaction. A later project-adoption gate must obtain a
fresh preimage before any live write; a rehashed local adapter is not authority.

## Creation, verification, and recovery

Create a new standalone Agent OS contract only in an empty or compatible
project directory:

```bash
python3 scripts/agent_os.py init --target <project-root> --project-name <name>
python3 scripts/agent_os.py verify --target <project-root>
```

For a Chief project, the normal initializer creates the same required
contract, and `scripts/init_project.py --target <project-root> --check`
includes Agent OS verification when its project state says `required`.
Verification is read-only: it rejects missing, stale, tampered, escaping, or
source-version-mismatched contract files instead of repairing them.

Standalone `scripts/agent_os.py` creation and migration preflight destinations,
stage replacements, and restore backed-up destinations if a write fails or is
interrupted. Chief fresh initialization and explicit migration additionally roll
back when their post-write project validation fails. If restoration itself fails,
the command retains the exact staged-backup path and reports recovery as
incomplete; do not delete or hand-edit that evidence. Otherwise, confirm the
pre-existing project files are intact, resolve the reported conflict or input
error, then rerun the same explicit command. Never delete a legacy project or
force a normal rerun to promote it.

`AGENTS.md` is the Codex/Chief adapter and is the only adapter that carries
Codex task, pin, automation, and Chief governance authority. `CLAUDE.md` is a
thin shared-core adapter only; it neither grants those authorities nor enables
or validates a live Claude runtime. Real-Claude execution, host integration,
and its separate acceptance gate are deliberately deferred from Agent OS V1.

## Codex-only activation candidate

`scripts/codex_agent_os_activation.py` is the V2 activation interface. It
requires explicit `plan`, `apply`, `verify --state activated|baseline`,
`rollback-plan`, `rollback`, and `recover` calls with caller-supplied absolute
source (for `plan`/`apply` only), Skills-root, global `AGENTS.md`, evidence-root, and a fresh 32-lowercase
hexadecimal transaction ID; it never assumes a user-home or machine-specific
location. The frozen global
marker block requires restoring local facts, reading nearby README,
implementation, tests, configuration and ownership, following the closest
valid pattern, using version evidence, running real commands, documenting
behavior, separating facts/inference/open items, asking about semantic
ambiguity, and persisting durable rules only through `RULE_CANDIDATE`.

The source is not a checkout: activation requires an extracted reviewed
candidate and an explicitly supplied frozen source-inventory hash. Source trees
containing checkout/control directories such as `.git` or `.superpowers` are
rejected. Evidence plan and receipt files live beneath an explicit separate
evidence root and cannot alias a managed target.

The plan inventories and hashes both surfaces. Apply creates identical immutable
`activation-intent.json` replicas in fixed package and global transaction roots,
stages exact content, then uses kernel no-replace renames. Recovery derives all
mutable paths only from the supplied roots and transaction ID, content-classifies
live/stage/backup/quarantine objects, and never recursively deletes or replaces
an unrecognized object. A rollback intent is one-way: interrupted rollback is
continued to the original baseline. Transaction and evidence objects are retained
after success; V2 has no cleanup command. The candidate validates Codex only.
`CLAUDE.md` is dormant static compatibility content, not a live authority or
runtime assertion. A future Claude activation needs independent E2E evidence
and an acceptance gate.

Every activation command requires a detached candidate manifest, a detached
`TESTING_GATE_PASS` from the privately provisioned Testing reviewer, and its
exact caller-pinned SHA-256. Mutating `apply` and `rollback` also require a
nonempty action-specific operator approval ID as immutable audit evidence.
The gate must name at least one recognized Testing lane. Once immutable intent
exists, recovery, verification, rollback planning, and rollback derive the
frozen source identity from it and can run after a disposable reviewed source
has disappeared. `recover` without a transaction intent is fail-closed: it
does not claim that an unfrozen baseline is verified.

## Private Testing authority provisioning

The public skill contains no live reviewer identity. Before consuming a Testing
receipt, delegation, legacy migration gate, or Agent OS activation gate, the
trusted host operator must set `CHIEF_PRIVATE_AUTHORITY_CONFIG_PATH` to an
absolute external file and `CHIEF_PRIVATE_AUTHORITY_CONFIG_SHA256` to that
file's lowercase SHA-256. The JSON is exactly:

```json
{"schema":"CHIEF_PRIVATE_AUTHORITY_CONFIG_V1","testing_reviewer_task_id":"operator-private-id"}
```

The configuration belongs outside the public skill, submitting project,
candidate, and native receipt/trust surfaces. It is selected only by the host
environment, never by a CLI argument, candidate, project, receipt, or
delegation. The consumer opens it without following a final symlink, validates
the opened descriptor as a one-link regular file, bounds it to 16 KiB, rejects
duplicate or extra JSON keys, and recomputes the independently supplied digest.
Missing, malformed, aliased, relocated, or hash-drifted configuration fails
closed; there is no public default or synthetic fallback. This publication does
not install the skill, provision authority, or change an existing host.

The supported Codex layout may place the Skills root beneath the global parent
(for example, `~/.codex/skills` beside `~/.codex/AGENTS.md`). Equal roots or
the inverse nesting are rejected. New rollback requires the exact fixed plan;
after both immutable rollback intents survive a crash, `recover` can still
return to baseline if that external plan is gone, reporting the evidence gap.
Its successful CLI object then contains
`"evidence_gap":"rollback-plan-missing; immutable rollback intents restored baseline"`;
this does not recreate or silently bless the missing external plan.
Approval IDs are exact immutable audit values; empty or leading/trailing
whitespace values are rejected before an activation or rollback intent is made.
Probe file/directory evidence remains transaction-scoped and is exercised only
through a held no-follow directory descriptor. Before activation intents, the
canonical probe-root pathname must still be the same non-symlink directory.
Without signatures this is not a defense against a caller who controls both
the executable and its arguments. Each per-surface rename is atomic only on its local filesystem. The two-surface activation/rollback is not globally atomic; it is journaled and recoverable.

Standalone migration can preserve arbitrary legacy `AGENTS.md` payload as
payload, but that CLI has no external authority anchor for its content: it
verifies only the deterministic wrapper, structure, hashes, and provenance.
In required Chief mode, `init_project.py --check` additionally accepts the
preserved payload only when it matches the current or a recognized historical
managed Chief contract; a rehashed payload change still fails that check.

## Shared contract and workflow

The manifest hashes the active Agent OS files and identifies a portable root
derived from the project name. Required-mode `--check` verifies the manifest,
adapters, source versions, safe in-project paths, and file hashes. A changed
shared core therefore requires deliberate regeneration rather than silently
trusting a stale adapter.

Use `scripts/agent_os.py verify` to validate a contract and optional packets.
Its packet boundaries are:

- `WORK_PACKET_V1`: a unique packet ID, objective, project-relative write
  surfaces, acceptance checks, and approval status.
- `RESULT_PACKET_V1`: a link to a supplied work-packet ID with the same task
  and root, verified facts, changed surfaces inside that packet's owned
  surfaces, evidence, status, and next step.
- `RULE_CANDIDATE_V1`: a proposed persistent rule with a non-empty, explicit
  operator approval ID before promotion.

Distinct concurrent work packets must not overlap a write surface, even when
they name the same task. Packet validation
does not itself approve a rule, production action, or Chief authority.

## Source policy and provenance

This integration derives its structure semantically from the Agent OS outline
in [nmnmcc's immutable gist revision](https://gist.github.com/nmnmcc/37c855a390166f8df441001b266ae2e1/f10729445d12ca586ed31f7ec50c257a0b336664)
(`f10729445d12ca586ed31f7ec50c257a0b336664`) and the repository-level
agent-entrypoint pattern in [Ceno's pinned AGENTS.md](https://github.com/nmnmcc/ceno/blob/cfc89848f505ad5cc6538021debaf3d9e595819b/AGENTS.md)
(`cfc89848f505ad5cc6538021debaf3d9e595819b`), accessed 2026-09-03. It
intentionally does not copy either source's wording or Ceno's code-style
rules. Chief governance remains this Skill's own contract; the shared Agent
OS core only supplies portable execution and packet boundaries.

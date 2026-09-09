# Work execution V1

## Applicability and adoption

Chief `2.0.0` declares schema `2` in `chief-version.json`, alongside `WORK_EXECUTION_V1`. New and synced projects use a thin managed entry and `.chief-of-staff/chief-lock.json` to pin the exact source commit. See the [installation and fleet-sync instructions](../README.md#chief-200-installation-and-explicit-fleet-sync). Generic rules live in this source, while `.chief-of-staff/project-overrides.md` holds user-owned project commands, business constraints, and stricter limits. Overrides cannot expand permissions, remove required validation, or erase history.

New projects default to `project.json.work_execution_version: WORK_EXECUTION_V1`. Existing projects retain their current behavior until their Chief explicitly rereads this contract and adopts it with a retained decision reference. Reading updated instructions alone, reinstalling the Skill, or running an ordinary initializer check does not adopt an old project. Adoption is in place: keep the current Chief, task identity, history, goal, authorization, approvals, ownership, and failure evidence. No restart or new task is required after explicit reread and successful adoption. This is not context migration.

For V1, the current work record in `project-plan.json.work_items` determines execution and discovery. This contract replaces legacy mandatory-child and whole-project production-discovery routing only for V1. It never overrides a denied action, unconfirmed goal, unresolved applicable product requirement, safety boundary, visual selection, protected action, or stricter existing budget. Legacy project classification and discovery evidence remain preserved and valid; a new work label cannot erase them.

Run these commands from the installed Skill or repository root, replacing the project path and retained decision reference:

```bash
python3 scripts/work_execution.py --target /path/to/project --preview-adoption
python3 scripts/work_execution.py --target /path/to/project --adopt --decision-ref 'user:approved-adoption-request'
python3 scripts/work_execution.py --target /path/to/project --check-work w1
```

Replace `user:approved-adoption-request` with the actual retained decision reference. Preview needs no decision reference and writes nothing. Apply requires a real retained explicit-adoption decision reference; the string itself does not authenticate approval. A zero exit code from `--check-work` means the current retained state permits an attempt, not that capacity was reserved, execution occurred, or acceptance passed. Use the callable `run_work(target, work_id, action)` to recheck and record a bounded attempt before invoking the caller's action.

Preview adoption, inspect conflicts, then apply only against the same current state. The adopter validates before writing, retains recovery evidence, and uses a transaction with idempotent retry and rollback on failure. A conflict or failed validation keeps the existing project authoritative. Apply checks current state again; an earlier preview is not permission to overwrite newer state. Adoption waits for a safe boundary and rejects paused projects or running registered tasks. It records `work_execution_adoption` with the decision reference and time. Sync replaces only recognized generated legacy instructions with the thin entry from `assets/chief-project-entry.md`; Git history preserves the old version. Unrecognized manual instructions are conflicts, not rewrite targets. For a managed Agent OS adapter, sync regenerates the canonical adapter and manifest around that thin entry. Independently frozen or gated adapters may require their existing revalidation path; adoption never bypasses that gate. Do not automatically migrate other projects, create successor tasks, install an automation, poll in the background, or infer user authority from adoption.

## Select execution by benefit

The Chief executes work directly when that is efficient. `DIRECT` is an execution mode, not a role, extra Chief, or child task. A Chief can satisfy active-work requirements through a registered current work item without creating a child merely to keep a phase active. The Chief records scope, acceptance, evidence, exclusive write surface, dependencies, and stop conditions before implementation.

Delegate only for an observable benefit: independent review, distinct expertise, separately usable long-lived context, or genuinely parallel work with lower elapsed cost than its coordination overhead. Record the expected benefit and reuse a suitable registered executor before creating one. The Chief retains central-state ownership; every output surface has exactly one writer. Neither direct execution nor delegation alters authorization. A self-executing Chief cannot also count as its own independent reviewer.

## Classify the current work

| Work kind | Required discovery |
| --- | --- |
| Operational work with settled requirements | Verify inputs, authority, acceptance, and effects; perform the operation. |
| Repair of established behavior | Reproduce or retain the failure, inspect the affected contract, and verify the correction. |
| Investigation of a technical unknown | Bounded evidence collection addressing the uncertainty that controls the next move. |
| New product | Full product discovery: initiation, requirements, market/user evidence, and advisory architecture feasibility. |
| Product change | Discover affected requirements, users, interfaces, constraints, and risks; reuse still-valid prior evidence for unaffected areas. |

Record why the classification fits the actual goal and change. Product changes that introduce a new product boundary require full discovery for that boundary. An operational or repair label does not permit a feature change or bypass an unresolved product decision. Escalate material unresolved choices through the existing route; independent safe work can continue.

Full discovery keeps the substance and evidence standards in [product-discovery-governance.md](product-discovery-governance.md). New-product full discovery retains the existing Product Manager phase lead and complete four-lane workflow required by the product-discovery schema. Direct execution applies to eligible established work and does not remove those full-discovery requirements. Discovery and review depth are separate decisions.

## Review according to risk and evidence

Low-risk, bounded, reversible work with adequate direct evidence may use self-review. Record what was checked, the result, and the exact artifact or state to which it applies. Risk, uncertainty, broad effects, or weak evidence can require independent review even when implementation is short.

Authentication, permissions, money, migration, irreversible changes, and other high-risk work require an independent reviewer with a distinct identity and no implementation ownership of the reviewed work. Reuse the registered evidence role when suitable. The review identity must resolve to a registered read-only task distinct from the writer. A title, delivery receipt, or a second pass by the writer is not independence. Review cannot grant product direction, visual selection, or protected-action authority.

## Finite budget and lack of progress

Before execution, the Chief sets finite work limits from user constraints, prior attempts, observed resource capacity, and uncertainty. Track consumption cumulatively for the same underlying work across writers, phases, candidates, retries, and renamed IDs. The checker shares attempts whenever work records overlap in final `acceptance_ids` or retain the same `work_id`, `goal`, or `lineage_id`, and applies the smallest retained applicable budget limit. Changing or combining acceptance bindings cannot erase the corresponding historical spend; the Chief must preserve the confirmed acceptance contract rather than relabel it to manufacture capacity. A phase-local allowance can coexist with the work limit but cannot renew it. Preserve stricter existing limits and failure history; any authorized budget change must retain the old limit and consumption with its decision basis.

Only a retained acceptance gain, removed blocker, or reproducible new cause is progress. Commentary, repeated receipts, a new candidate hash without a gain, and reassignment are not progress. After two consecutive stagnant rounds, stop repeating that path and obtain independent diagnosis. Resume only on an evidence-backed new path within the remaining budget and authority. Exhausted budget blocks affected execution; do not bypass it through a new phase, owner, work ID, or discovery label. Continue independent safe work where admitted.

## Resource admission

Classify heavy work from its expected memory/CPU demand and current pressure, not a machine or device name. The current checker consumes explicit memory headroom, heavy-task capacity, and retained observation evidence; it does not independently sample memory, CPU, or system pressure. Build, browser, emulator, and broad test workloads can compete for the same resources. Use fresh resource observations and reserve capacity for admitted heavy work; unknown resource capacity defaults to at most one heavy task. In `throughput.json.resource_observation`, provide `observed_at` with a timezone, positive integer `heavy_limit` and `available_memory_mb`, and a retained `evidence` proof. The freshness window is 300 seconds: stale, future, or malformed observations reject heavy admission until refreshed. Missing observations default to one heavy task; an unknown memory estimate also limits heavy concurrency to one. Requested plus running heavy memory estimates must fit the observed headroom. A reservation or check is not a process scheduler or proof that a process launched.

When a heavy task is denied admission, queue it and continue nonconflicting lightweight reading, planning, editing, or evidence review when safe. Preserve one writer per surface and all dependency boundaries. Check again at the next authorized action boundary; this contract does not create background polling or automatic process management.

## Build and release

Use [build execution governance](build-execution-governance.md) for the callable helper and its adapter obligations. Static checks precede expensive builds. Once a build produces an artifact, retain it with provenance before validation; failed checks keep evidence and the artifact available. Build eligibility, verification success, and release authorization are separate. Critical validation or signing failures prohibit release. An APK-only task does not require or generate an AAB unless separately in scope. A retained artifact is not automatically a verified or publishable artifact.

## Proof obligations

Verify direct execution with no artificial child; reject overlapping writers; exercise each discovery class; require independent high-risk review; detect two stagnant rounds and accumulated budget exhaustion; admit lightweight work while heavy capacity is unavailable; and prove adoption conflict handling, idempotency, rollback, and preserved legacy state. Work history and metadata are coordinator-owned records, not tamperproof authority. The checker validates retained file hashes, record structure, and admission decisions; it does not authenticate the author, prove the meaning of evidence, independently inspect repository provenance, or enforce actual operating-system scheduling. Use direct retained evidence for those claims.

## Record shape and minimal queued-work example

The project has `work_execution_version: WORK_EXECUTION_V1`; the confirmed active plan already contains phase `p1` and final acceptance criterion `apk`. Add the following object to `project-plan.json.work_items`, and initialize `work_history` to `[]` only for genuinely new state. Never clear historical events. The example is a queued operation awaiting final package acceptance, not a completed or released artifact.

Each evidence object is `{ "ref": "repo://relative/path", "sha256": "<actual lowercase SHA-256>" }`. Its file must exist inside the project, match the digest, and be a regular file with one hard link and no symlink path components. The example hash is for an `evidence.txt` containing exactly `approved existing behavior and verified result` with no trailing newline; it illustrates the fixture shape. Replace that illustrative text with real retained evidence, then recompute the digest. The input example uses a `source.txt` containing exactly `existing app source` without a newline. Replace fixture files with real inputs and recompute all hashes. Source repository/revision are explicit caller-supplied provenance, not a prescribed repository or an automatic clone; use the actual source for this work. Neither a repository name nor its source organization changes discovery, authorization, or acceptance requirements.

```json
{
  "work_id": "w1",
  "phase_id": "p1",
  "goal": "Package existing source",
  "acceptance_ids": [
    "apk"
  ],
  "kind": "operation",
  "status": "queued",
  "source": {
    "repository": "https://example.test/actual.git",
    "revision": "abc",
    "evidence": {
      "ref": "repo://evidence.txt",
      "sha256": "7ec7b6f6e6c53f7c3540883ba6d416d3f5b37f28c49693024cd7935918f5b33e"
    }
  },
  "executor": {
    "kind": "chief",
    "id": "Chief of Example"
  },
  "write_surface": [
    "artifacts"
  ],
  "input_sha256": "1ccd6b2750d4519635f5243de7ac872d7615ac66e75e28d5dec5e48c223934fe",
  "risk": {
    "level": "low",
    "domains": []
  },
  "discovery": {
    "basis": "existing",
    "evidence": [
      {
        "ref": "repo://evidence.txt",
        "sha256": "7ec7b6f6e6c53f7c3540883ba6d416d3f5b37f28c49693024cd7935918f5b33e"
      }
    ],
    "unresolved_product_decisions": [],
    "affected_areas": [],
    "existing_behavior_confirmed": true
  },
  "prechecks": [
    {
      "name": "static",
      "status": "passed",
      "input_sha256": "1ccd6b2750d4519635f5243de7ac872d7615ac66e75e28d5dec5e48c223934fe",
      "evidence": {
        "ref": "repo://evidence.txt",
        "sha256": "7ec7b6f6e6c53f7c3540883ba6d416d3f5b37f28c49693024cd7935918f5b33e"
      }
    }
  ],
  "acceptance_checks": [
    {
      "name": "package",
      "status": "pending",
      "input_sha256": "1ccd6b2750d4519635f5243de7ac872d7615ac66e75e28d5dec5e48c223934fe",
      "evidence": null
    }
  ],
  "review": {
    "mode": "self",
    "reviewer": "Chief of Example",
    "evidence": [],
    "input_sha256": "1ccd6b2750d4519635f5243de7ac872d7615ac66e75e28d5dec5e48c223934fe"
  },
  "budget": {
    "limit": 3,
    "reason": "Historical package checks finish within three attempts"
  },
  "resources": {
    "weight": "heavy",
    "memory_mb": null
  },
  "lineage_id": "package-lineage",
  "inputs": [
    {
      "ref": "repo://source.txt",
      "sha256": "944ff8facb074647da39e108ddd623ee96765b75d129f47d6b041fc2621ba799"
    }
  ]
}
```

The accepted field vocabulary is:

| Field | Contract |
| --- | --- |
| `work_id`, `lineage_id`, `phase_id`, `goal` | Nonempty identity, stable work lineage, an existing phase ID, and the observable goal; work IDs are unique. Preserve lineage across continuation. |
| `acceptance_ids` | Nonempty unique IDs of existing final plan acceptance criteria; overlapping IDs share attempt consumption. |
| `kind` | `operation`, `repair`, `investigation`, `new_product`, or `product_change`. |
| `status` | `queued`, `running`, `needs_attention`, `blocked`, `completed`, or `cancelled`. |
| `source` | Nonempty `repository`, `revision`, and one retained `evidence` proof. |
| `executor` | `kind: chief` with the configured `primary_task_id`, falling back to `primary_task_title` when absent; or `kind: task` with an existing task ID bound to the same phase, `execution_work_id`, and write surface. |
| `write_surface` | Project-relative normalized POSIX paths; reject absolute paths, parent traversal, or symlinks. Investigation uses `[]`. |
| `inputs`, `input_sha256` | Nonempty ordered list of retained file proof objects, plus SHA-256 of `json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode()`. The current input files are rehashed at admission; current checks and review bind that manifest hash. |
| `risk` | `level: low`, `medium`, or `high`; `domains` contains only `authentication`, `permissions`, `funds`, `migration`, or `irreversible`. Any listed sensitive domain requires independent review. |
| `discovery` | `basis`, retained `evidence`, `unresolved_product_decisions`, and `affected_areas`. Operations/repairs use `existing` with `existing_behavior_confirmed: true`, investigations use `targeted`, new products use `full`, and changes use `affected` with named affected areas. |
| `prechecks`, `acceptance_checks` | Nonempty lists with unique `name`, `status: pending/passed/failed`, `input_sha256`, and `evidence`. Passed checks require retained proof. Admission requires passed current-input prechecks; completion requires passed current-input acceptance checks. |
| `review` | `mode: self/independent`, `reviewer` identity, `input_sha256`, and retained `evidence`. Self-review identifies the writer; independence requires a distinct registered task ID whose registry write surface is empty. Completion requires current-input review evidence. |
| `budget` | Positive integer attempt `limit` and nonempty causal `reason`. Historical smaller limits remain controlling. |
| `resources` | `weight: light/heavy` and positive integer `memory_mb`, or `null` when unknown. |

A new-product work item requires the full product-discovery state to pass as well as its `basis: full` record. A current-work classification does not mark the whole project discovered or waive unmet requirements. `product_change` requires affected-area discovery. Unresolved product decisions block execution except a read-only targeted investigation that exists to resolve them. The coordinator remains responsible for honest classification and evidence meaning.

For a retry, add `retry.correction` (the changed corrective action) and `retry.cause` (a new retained proof). Reusing an already-consumed cause hash does not qualify. After two stagnant attempts, `retry.diagnosis` must contain `reviewer`, the two exact chronological `event_ids`, a nonempty `new_path`, and retained `evidence`; the reviewer must resolve to a registered task with an empty write surface and differ from the current executor and every historical writer for this work.

`run_work` appends `work_history` events with `event_id`, `work_id`, `lineage_id`, `goal`, `continuity_key`, `acceptance_ids`, `executor_id`, `input_sha256`, `budget_limit`, `status` (`running`, `finished`, or `failed`), `progress`, and `cause_sha256`. It records spend before calling the action; failure does not refund it. Unresolved running attempts block retries until observed and reconciled. An action may return a typed `progress` object: `kind` is `acceptance_gain`, `blocker_removed`, or `reproduced_cause`; `criterion_id` binds an accepted outcome; nonempty `before` and `after` must differ; `evidence` is a retained proof. A duplicate evidence hash does not reset stagnation. The caller must ensure it represents an actual acceptance gain, resolved blocker, or reproducible new cause. Returning normally does not complete work: the record returns to `needs_attention` for evidence-based closure.

Existing continuous-execution packages keep their own authorized consumer; this admission path rejects those projects rather than becoming an alternate authorization route. The work helper and instructions do not create a daemon, automatically discover every project, or promise runtime enforcement outside calls that actually use the helper.

`check_work` compares the source HEAD/version pin and retained managed-file hashes; it does not itself reject every dirty file in the source checkout. Fleet sync separately requires a clean fixed-tag source. These checks do not guarantee future agents will read or obey instructions; the coordinator must verify the active source and use the relevant consuming path.


At candidate admission, current product-gate conditions remain relevant to established operations and repairs. If a blocked, conditional, or materially conflicted product gate does not affect this work, record optional `discovery.unaffected_by_current_gate` with `gate_sha256`, exact `acceptance_ids`, exact `write_surface`, nonempty `reason`, and a retained `evidence` proof. Compute `gate_sha256` as SHA-256 of the entire current product-discovery object encoded with `json.dumps(discovery, sort_keys=True, separators=(',', ':')).encode()`. Changing the gate, acceptance binding, or owned surface invalidates that mapping. This explicit evidence mapping permits unrelated established work; it does not waive affected requirements. New products still require the current full passed gate. Read-only targeted investigation remains available to resolve uncertainty. Current global conditions are checked at admission rather than retroactively invalidating completed historical records or every queued item.

# Neo 8GB private branch

`neo-8gb-lean` is a personal execution profile, not a replacement for upstream `main`. It retains the Full Chief source, discovery validation, role contracts, approval boundaries, Agent OS and context migration. There is no model/pricing change or claim of measured memory savings. The limits are agent instructions, not an OS process scheduler or a new deterministic task classifier.

## Entry points and defaults

The single routing contract is `assets/neo-lean-router.md`. It is installed verbatim in Neo's global `AGENTS.md`, read before the Chief skill, and embedded by `init_project.py` in newly generated project instructions. A skill description alone cannot establish a default for tasks that never invoke the skill.

| Task | Route and behavior |
| --- | --- |
| Existing APK build/package/run | DIRECT, no Chief initialization or new discovery |
| Coupled debugging across several files | LEAN, one writer; optional one read-only verifier after heavy build |
| One architecture uncertainty, no other coordination need | LEAN; one signal does not qualify for CHIEF |
| New product with independent UI/backend work and unresolved product decisions | CHIEF; retain product discovery and required approval gates |
| Explicit Chief request for already-decided build commands | CHIEF coordination-only with a concrete exemption reason |
| Substantive fix inside an existing governed project | Retain parent authority and existing discovery evidence; no bypass of a missing gate |
| All required deliverables and checks passed, optional polish remains | Stop and report; await human final acceptance if required |
| Initial same-class failure plus two retries | Stop that action; no fourth attempt through phase/agent rename |

At most one active phase lane and one active writer apply even in CHIEF. Logical discovery lanes and durable specialist roles remain available but do not grant parallel build capacity. DIRECT has no subagents; LEAN permits at most one read-only verifier with a concrete evidence benefit and no heavy-build overlap. Every repeat investigation or retry must pass the Information Gain Gate. `auto_advance_low_impact=true` advances authorized unfinished work; `proactive_follow_up=false` disables unsolicited background follow-up, not completion of the current request.

Fresh project JSON and missing-field defaults use one phase lane. Fresh projects disable proactive follow-up. Existing custom project state, personal preferences, automations and host model settings are not silently rewritten by pulling this branch; the installed router constrains larger legacy execution allowances on Neo. No live automation is created, modified or cancelled by installation. Existing governed projects keep their original approval and discovery state. Do not use ordinary-task routing to detach a child from its parent contract.

## Get the branch on Neo

For an existing clean clone of this repository:

```bash
git fetch origin
git switch --track origin/neo-8gb-lean
git pull --ff-only
```

If the local branch already exists, use `git switch neo-8gb-lean` instead of `git switch --track ...`. If Git reports uncommitted changes, preserve those changes before switching; do not reset them. Confirm the remote is `https://github.com/rong2qi/chief-of-staff-codex.git` with `git remote -v`.

For a fresh clone:

```bash
git clone --branch neo-8gb-lean --single-branch \
  https://github.com/rong2qi/chief-of-staff-codex.git chief-of-staff-codex
cd chief-of-staff-codex
```

## Enable the default (Neo only)

Use the branch checkout as the installed Chief skill. If `~/.codex/skills/chief-of-staff` already exists, inspect whether it is a checkout, copy, or symlink first. Switch an existing checkout to this branch, or preserve the old installation before replacing a copy/link. Do not create a nested `chief-of-staff/chief-of-staff` directory. For a previously uninstalled skill, from the repository root:

```bash
mkdir -p "$HOME/.codex/skills"
ln -s "$PWD" "$HOME/.codex/skills/chief-of-staff"
```

After pointing the skill to this checkout, install the global router:

```bash
python3 scripts/install_neo_router.py --target "$HOME/.codex/AGENTS.md"
```

The installer uses only the standard library and the repository's existing atomic writer. It prepends or refreshes one marked block and preserves other instructions, including the preferences block. Duplicate, incomplete, reversed markers or symlinked target paths fail without rewriting the target. For a symlinked AGENTS file, explicitly select its intended real `AGENTS.md` path. It does not install or invoke the optional companion skill; the core Lean discipline is already included. Open a new task to load the updated instructions.

After each branch update, rerun the installer to refresh the copied global block. To remove only the router:

```bash
python3 scripts/install_neo_router.py --target "$HOME/.codex/AGENTS.md" --remove
```

Switching the repository back to `main` alone does not remove an installed global block; remove it first when returning this machine to upstream behavior. Existing Neo-generated projects keep their embedded instructions until separately migrated.

## Verification and maintenance

The full suite requires Python 3.11+ (the macOS default Python may be older):

```bash
python3.11 -m unittest discover -s tests -q
git diff --check
```

Regression coverage exercises installer preservation/idempotence, unsafe-input refusal, fresh initialization and existing Full Chief validation. Scenario review checks routing, discovery boundaries, retries, acceptance and concurrency. These checks do not measure actual APK build speed or prove every future agent decision.

Keep changes to this branch. Update from `main` deliberately on a clean Neo branch, resolve router/default conflicts, rerun validation and refresh the global block. Do not merge Neo specializations into `main`.

## Build management follow-up

Build execution governance is part of `neo-8gb-lean`; use this existing branch for all Neo execution improvements. Do not create another delivery branch for this mode. See [build execution governance](build-execution-governance.md). These are management instructions, not Android application scripts. Both new projects and a refreshed global router receive the contract; existing project instructions are not silently migrated.

After updating the checkout used by the installed skill, rerun `python3 scripts/install_neo_router.py --target "$HOME/.codex/AGENTS.md"` and open a new task. Preserve any other installed skill copy before replacing it. Use the branch retrieval instructions above; keep unrelated dirty work intact. Existing history remains unchanged.

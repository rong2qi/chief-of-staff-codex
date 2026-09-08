# Lifecycle capability discovery

Use this policy when `project_start_capability_discovery.enabled` is true. The key name is retained for schema-version-1 compatibility. The policy prevents registered Chiefs from rebuilding capabilities that already exist while preserving every acquisition, permission, external-action, and production gate.

## Compatibility modes

- **Legacy startup mode:** a section without lifecycle-only fields keeps the original broad project-start scan and one stack-specific confirmation before production execution. Its existing acquisition wording remains valid for old profiles, subject to the approval boundaries that existed when those profiles were created.
- **Lifecycle mode:** any lifecycle-only field selects the new contract, so every required lifecycle field must be present and exact. Partial or weakened lifecycle input fails closed. Its `acquisition_policy` is `discover_and_recommend_only`.
- A missing section is disabled. Public example and bilingual preset files intentionally remain legacy-shaped and anonymous; enabling the stricter live mode requires the deterministic configurator.

## Scope and triggers

Lifecycle mode covers every registered Chief with a project or coordination responsibility domain. It runs only for active unfinished work and at these exact events:

1. `project_start`
2. `phase_or_stack_change`
3. `repeated_manual_work`
4. `blocker_or_failure`
5. `before_custom_build`
6. `before_production_execution`

Paused projects defer discovery until resume. Completed and archived work is excluded and never reactivated. A previous refusal, pause, permission boundary, or operator denial always wins.

## Search surfaces

Search only as deeply as the trigger and evidence require, across:

- host and installed capabilities, Codex Apps, Connectors, MCP servers, plugins, and Skills;
- official APIs, SDKs, CLIs, frameworks, libraries, documentation, and reference implementations;
- maintained open-source projects, templates, starters, reference implementations, and design systems;
- host/project runtimes, emulators, browsers, scripts, caches, builds, containers, devcontainers, and disposable VMs;
- compliant datasets, model assets, evaluation sets, and prompt libraries;
- testing, evaluation, security, performance, reliability, and observability capabilities;
- CI configuration, runbooks, SOPs, and architecture patterns;
- SaaS, managed, and cloud offerings for research only;
- experts, maintainers, and service providers for discovery only, without contact.

## Serious-candidate evidence

Every serious candidate records a traceable source and fixed version or revision, fit, benefit, maintenance evidence, license, supply-chain risk, permissions, privacy, secrets handling, cost, integration and lifecycle impact, overlap, and an exit/removal path. Do not invent maintenance, market, security, privacy, compatibility, interview, or benchmark evidence.

Each Chief-trigger pair produces at most one deduplicated recommendation pack and at most three candidates. No worthwhile candidate, all-reject, and routine scans remain internal evidence and do not enter TODO. A material recommendation routes through the general office; a testing-related candidate goes first to the sole Testing Director; visual direction remains exclusively with the Creative Director.

## Discover-only acquisition boundary

Lifecycle mode may discover, evaluate, and recommend. It does not authorize installation, pull, download, enablement, account connection, dependency addition, payment, external contact, external send, production execution, or project mutation. It never uses a candidate in production or changes a business project under discovery authority.

If adoption is later approved, prefer project-local installation or configuration. Global installation and every protected action require the operator's separate explicit approval. Treat third-party code and configuration as untrusted, fix selected versions or revisions, preserve lockfiles, keep one writer, and define removal before adoption.

## Execution limits and reporting

- Run at most two independent scans in parallel.
- Deduplicate by Chief, trigger, and evidence identity before routing.
- Report only material recommendations; keep routine progress and negative results in the internal evidence index.
- Discovery cannot create a user TODO by itself. The authoritative general office or Creative Director applies the normal actionable-now gate.
- Testing review is evidence-only and does not install a candidate, take project write ownership, or become a second operator-facing hub.

Discovery evidence is a prerequisite for deciding whether to reuse, adapt, or build; it is never acquisition or production authorization.

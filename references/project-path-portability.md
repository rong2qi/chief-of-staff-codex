# Project path portability

Use this contract for active project code, scripts, configuration, tests, current instructions, and active manifests or indexes. It keeps a project native after a copy or clone to a different parent directory or device. It does not authorize editing an existing business project.

## Resolve the project root

Resolve the active root in this order:

1. A project-specific environment variable supplied by the caller, when present and valid.
2. The enclosing Git worktree root, when available.
3. An upward search from the script or configuration location for a project marker, `AGENTS.md`, or `.chief-of-staff/project.json`.
4. The current project working directory as a compatibility fallback.

An environment variable is an optional override, never a setup prerequisite. Moving or cloning the project must preserve native read/write behavior without setting one. Never use a fixed volume mount, user-home location, temporary directory, drive prefix, machine username, or launch-time directory from another device as a default root.

## Represent active paths

- Give the root a stable `root_id` derived from declared project identity or a stable repository identity, never from its absolute location.
- Store active project paths as normalized project-relative POSIX paths. Reject absolute input, parent traversal, platform drive syntax, empty or ambiguous segments, and any resolution that escapes through a symlink.
- An environment override can select a valid root; it cannot weaken the project boundary or path checks.
- Keep active manifests and indexes portable. A copied project must write its safe outputs beneath its newly resolved root, not the old parent.

The library helper `scripts/project_paths.py` implements this contract without scanning the wider filesystem. It is a reusable primitive, not a command and not authorization to rewrite business state.

## Register external tools and materials

Do not copy external SDKs, browsers, emulators, tools, or source materials into the project merely to make paths look relative. For each use, register the exact external identity and path, granted permissions, and authorization. The record must state that the external location is not the project root or a project-root prerequisite. Reject unregistered absolute paths and incomplete registrations.

## Preserve historical evidence

Absolute paths inside a historical audit, frozen candidate, hash manifest, context migration bundle, legacy build, or provenance record describe what happened at that time. Preserve that evidence unchanged. Separate it from the active runtime surface and never read it as a default root.

When a portable form is needed, create a new derived candidate with its own hash and a `derived_from` field containing the immutable source hash. Do not rewrite the historical record or silently relabel it as active state.

## Verification boundary

Test root discovery and path containment in a disposable copy. Any runnable or clickable portability candidate offered to the operator still needs an exact-hash `TESTING_GATE_PASS` from the registered Testing Director. Documentation and templates describe the contract; they do not claim that an existing business project has passed it.

<!-- chief-managed:start -->
# Chief of Staff project entry

Chief is the single source of generic behavior. This project pins the installed Chief source through `.chief-of-staff/chief-lock.json`; verify its version and commit before applying rules. Locate the installed `chief-of-staff` skill checkout, not a repository path mentioned in incident logs. If its commit differs from the pin, use the pinned source or explicitly sync; never silently follow floating main.

Read that source's `SKILL.md` and `references/work-execution.md` for the current work. Product classification and discovery gate, review, resource and build rules live there, not in a copied project policy. Project state and history remain under `.chief-of-staff/`.

Read `.chief-of-staff/project-overrides.md` if present for project-specific commands, business constraints and stricter limits. This file is user-owned. It cannot expand permission, redefine generic Chief authority, erase failures, or waive required validation. Conflicts are reported rather than overwritten.

Use the source's `scripts/chief_sync.py` for explicit single-project or fleet migration, dry-run and rollback. Continue the existing Chief task after explicitly reading the pinned rules; no new Chief is required. Sync does not run business builds or grant release permission.

Use the pinned source's `references/testing-evidence.md`, `references/testing-control.md`, `scripts/testing_evidence.py`, and `scripts/testing_control.py` for evidence-aware, risk-based Testing. Freeze original evidence, inherit unaffected PASS, and require a changed input, dependency impact, or explicit new risk before sending only `RETEST_REQUIRED + INTEGRATION_ONLY`. L0 is deterministic/local; L1 is local by default; L2 is targeted and non-blocking; L3 or `SYNC_TESTING_REQUIRED` blocks only its dangerous action. Testing telemetry is record-only, pending never idles unrelated work, and infrastructure delivery gets one retry before `TESTING_INFRA_ERROR`.
<!-- chief-managed:end -->

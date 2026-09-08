# Recommended-action standing delegation

This optional policy reduces operator noise without transferring reserved powers. It is disabled when the section is absent or `enabled` is not exactly `true`. The general office is the sole authority owner and may delegate only one clear, evidence-complete, fixed-surface, nonproduction recommendation from the configured allowlist.

It does not replace enabled autonomy policy: that policy lets the source Chief continue ordinary preparation, evidence collection, and bounded candidate-defect recovery under a previously approved, revalidated package. It never creates new permission or overrides a protected stop.

## Eligibility and audit

Every delegated action must have one stable ID, exactly one recommendation, complete evidence, an exact identity and write/read surface, any applicable independent verification, no unresolved safety dissent, no production target, no real customer or personal data, no credentials or secrets, an explicit `external_send=false`, and explicit stop and rollback conditions. Record:

`DELEGATED_RECOMMENDATION_EXECUTED: <stable_id>`

Return that marker to the source Chief. Do not emit `USER_ACTION_REQUIRED`, a suggested operator reply, or a TODO item. Failure, identity/hash drift, scope expansion, or a requested automatic rerun stops the action; it does not authorize another attempt.

Class-specific evidence is mandatory:

- Exact task-owned cleanup requires an absolute exact path, `file_type=regular_file`, fresh byte size and SHA-256, non-symlink proof, no glob, no recursion, and proof that the file is a temporary artifact created by that task.
- Metadata-only read requires an exact target, a non-empty fixed read allowlist, positive response-byte and time caps, `read_only=true`, `write_allowed=false`, empty write roots, token non-persistence, an exact stop condition, and class-specific independent verification.
- Fixed-hash one-shot execution requires an exact SHA-256, an explicit I/O allowlist, no overwrite, zero prior executions, and no automatic rerun.
- Disposable local testing requires an absolute exact disposable target, disposal proof, a fixed I/O allowlist, a positive timeout, an exact stop condition, explicit rollback steps, one allowed run, zero prior runs, and no automatic rerun.
- Bounded repair/recheck requires a frozen candidate SHA-256, the exact repair target, one unique existing write owner/surface, no ownership conflict, explicit no-scope-expansion proof, exactly one not-yet-used repair plus one not-yet-used recheck, no automatic rerun, and failure-stop behavior.

## Reserved powers

The operator alone decides final goals or material product direction, visual selection, final acceptance or termination, Chief appointment/pause/removal/pinning/replacement, payments or purchases, release/deploy/production/rollback, external communication/new collaborators/public visibility, credentials/secrets/real identity/sensitive data, legal/privacy/material-security risk acceptance, real-user or production-data deletion, recursive/broad/irreversible deletion, write-ownership conflicts, work still failed or unverifiable after the allowed repair/recheck, and any override of a prior explicit operator denial.

Prior explicit denial always wins. A non-unique recommendation, incomplete evidence, or unresolved audit/safety dissent returns to the source for evidence; it is neither delegated nor operator-actionable until a reserved decision is genuinely ready.

## TODO projection

TODO shows only records with `operator_actionable_now=true` from the authoritative general-office or Creative Director hub after evidence completeness, exact identity/surface, and absence of unresolved safety dissent are independently present. Exclude delegated/resolved items, evidence gathering, routine reports, ordinary failures, internal retries, ordinary test results, unavailable entries, and non-authoritative copies. If Testing is applicable, require the exact frozen candidate to have `TESTING_GATE_PASS`.

A visual selection is actionable only in the Creative Director hub when its clickable entry is available, the candidate hash is frozen, and Testing has passed that exact hash. Otherwise keep it out of TODO rather than presenting a choice the operator cannot actually make.

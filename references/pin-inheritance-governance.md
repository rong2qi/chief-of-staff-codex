# Chief pin inheritance governance

Every active Chief is a pinned authoritative entry. Pinning is an independently verified state, not an API receipt.

## Verification rule

After calling the thread pin operation, call `list_threads` and require the Chief's exact task ID to appear in `pinnedThreads`. A result such as `pinned: true` only proves that the operation was accepted; it cannot prove the visible pin state. Record a failed independent check as `pin_verification_failed` in the Chief status and decision evidence.

The current Chief must remain pinned throughout its authority. Do not treat a manual unpin, stale list result, or a title match as sufficient. Resolve and compare the exact task ID.

## Successor authority gate

A migration candidate does not become authoritative merely by returning `MIGRATION_READY`. After migration parity is verified, but before accepting takeover, switching the authoritative user entry, or archiving the predecessor:

1. Pin the successor by exact task ID.
2. Call `list_threads` independently.
3. Require that exact successor ID in `pinnedThreads`.
4. Only then accept takeover and archive the predecessor.

The parity handoff includes the goal, phase, pending approvals and TODOs, write ownership, evidence, task graph, Git state, next checkpoint, pause state, and applicable global rules. Pin inheritance cannot approve an action, change scope, transfer unverified ownership, or resume a paused project.

## Failed verification

If the exact-ID check fails, the candidate does not take control. Record `pin_verification_failed`. At a safe handoff boundary, keep all failed or predecessor tasks recoverable and non-duplicated, archive the old authoritative Chief with reason `unable_to_pin`, and create exactly one replacement successor in the same saved project and existing work state. Transfer the complete parity handoff, pin the replacement, and repeat the independent `pinnedThreads` check before it takes control.

Never delete the predecessor or failed candidate. Never keep duplicate active Chiefs, create the replacement in a different project, change the project scope, clear or restore pause state, or use the migration to bypass a review or protected-action gate.

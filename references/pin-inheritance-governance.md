# Narrow Chief pin governance

Pinning is scarce operator-controlled navigation state, not a universal Chief health signal. Ordinary Chiefs default to unpinned. Their unpinned state is not a defect and cannot trigger a successor, a manual-pin request, or predecessor archival.

## Eligible roles

The only mandatory core roles are `general_office`, `todo`, `creative_director`, `context_migration_monitor`, and `testing_director`, including a verified valid successor in the same lineage. The Testing Director is the cross-project quality-policy and evidence-review core role; it reports through the general office and is not an independent operator-facing approval hub or project writer. Optional product Chief slots default to six, but observed capacity and protected manual pins are authoritative. An optional Chief may be appointed, pinned, unpinned, replaced, or inherit a slot only after a general-office recommendation and the operator's explicit approval of that exact change.

Grandmothered optional Chiefs may preserve their current pin until value review. Grandmothering grants no automatic successor inheritance and public files never contain their live IDs. Paused, completed, superseded, migration-cancelled, routine-push, meeting-summary, report-only, and process-only Chiefs are excluded by default; the central context migration monitor remains mandatory.

## Recommendation and capacity

The general office owns one pending recommendation pack containing at most three candidates. TODO performs read-only checks of exact identity, currentness, duplication, evidence freshness, observed capacity, and lineage. It neither appoints nor pins.

Protect every manual non-Chief pin. When capacity is full, issue only a paired replacement recommendation against an approved or grandmothered optional slot. Never evict automatically, and never treat full capacity as a task defect.

Pin approval is narrow: it does not confirm the project goal, approve the Product Manager brief, pass product discovery, or authorize engineering, design, content, production, a protected action, or a visual choice. A nonexistent optional Chief is created only after appointment and pin approval; it still begins behind the normal goal-confirmation and product-discovery gates.

## Verification and successor gate

A pin operation receipt such as `pinned: true` is not proof. For a mandatory core role or operator-approved optional lineage, call `list_threads` and require the exact task ID in `pinnedThreads`. Record a failed independent check as `pin_verification_failed`. This status is invalid for an ordinary or unapproved Chief.

Only an eligible mandatory or approved lineage can replace a failed successor. After a safe same-lineage core bundle handoff candidate, create at most one replacement. Transfer the goal, phase, pending approvals/TODOs, write ownership, evidence, task graph, Git state, next checkpoint, and pause state. Verify automation parity and the replacement's exact ID in a fresh `pinnedThreads` result before final `MIGRATION_READY`, takeover, authoritative-entry switching, or predecessor archival. A configuration reference or automation update receipt is not proof. Any automation mismatch records `automation_rebind_failed`, returns `MIGRATION_BLOCKED`, and keeps the predecessor active and unarchived. Archive the predecessor only after verified takeover.

Never delete predecessors, create duplicate Chiefs, move to a different saved project, change scope or pause state, restore a paused project, or use pin inheritance to bypass an approval. Failures created under the superseded broad pin rule do not continue.

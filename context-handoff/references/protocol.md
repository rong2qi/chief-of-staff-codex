# Rollover protocol

1. Re-read the newest token event. Continue rollover only at 85% or above, at a safe boundary, with write owners identified.
2. Capture exact IDs and distinguish facts, inference, questions, unsuccessful attempts, approvals, active roles, Git state, tests, risks, and the next action. Reference the immutable session by path and SHA-256 instead of copying it into the prompt.
3. Build atomically and verify every checksum. Rebuild once if the session changes during capture.
4. Prefer a clean task in the same saved project using the proven working-tree state. A same-history fork preserves continuity but is not a clean context reset.
5. Require `MIGRATION_READY`. Pending approvals stay pending, children keep their Chief/phase, and write ownership does not change merely because the conversation changes.
6. After parity, pin the successor when applicable, leave a redirect, and archive the predecessor. On mismatch, keep it active and retry once.


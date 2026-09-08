# Delivery ledger candidate

`scripts/delivery_ledger.py` is a local, Chief-owned journal. It has no
transport adapter and cannot send work. A host adapter may ingest a real tool
receipt as `TRANSPORT_ACCEPTED` only with a local stable `attempt_id`, exact
tool name, exact target identity, and a retained readable evidence file inside
the ledger surface. The event binds its hash to the evidence's actual accepted
tool observation; a hash-shaped caller assertion is insufficient. That is not
a receiver ACK. `RECEIVER_ACK_OBSERVED` requires a separately retained,
receiver-authored observation for that same accepted attempt and must name the
durable return target task. The target authors the ACK while the durable source
Chief may retain and ingest that native observation; author and observer are
distinct. A temporary native transport sender/observer is not automatically
the durable `return_to` Chief.

Run `ingest`, `check`, or `reconcile` with an explicit ledger directory. A
reconcile result is an identity-bearing intent for the host/Chief to act on; it
never dispatches, approves, or retries work. An empty or null native summary is `COMPLETION_OBSERVATION`
and remains `completed_unobserved` unless independent absence evidence justifies
`COMPLETED_EMPTY`; it must not trigger blind replay.

`NO_NEXT_STEP_DECIDED` and `COMPLETED_EMPTY` also require retained,
identity-bound evidence, after the relevant review/approval path. The journal,
not its snapshot cache, is authoritative. A strict adopted project reconciles
at each active turn, cold start, and authorized heartbeat: collect every unseen
child result using saved opaque cursors, ingest only retained receipts/ACKs and
reviews, then take the strongest already-authorized safe continuation or record
the exact blocker. This is a bounded sweep, not a persistent wait or host wake.

Use `retry_policy.py --project <root> consume` only with the stored repair
contract and a stable reviewer identity plus a fresh review-event ID. The first
independent review is free; an explicit one-shot, failure-stop, exhausted, or
smaller numeric bound wins. Consumption records budget only; it does not send
or approve a next action.

For an explicitly recorded continuous execution package, the same retry
consumer accepts a fourth-or-later cycle only with retained, distinct real
progress evidence and inside the package's finite bounds. Reconcile returned
receipts against the current work ID/package/return ID before any host action;
the local result is still an intent, never a dispatch. See
[continuous-execution.md](continuous-execution.md).

SHA-256 values demonstrate input integrity only. They do not establish external
provenance or replace the required Testing gate, review, approval, or real host
observations.

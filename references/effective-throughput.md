# Effective throughput

`effective_throughput` values completed, evidence-backed acceptance over task count. Keep at most two independent phase lanes by default, never share a write surface, and record the active lanes in `throughput.json`.

At every checkpoint, attach concrete evidence to the acceptance criterion. If two consecutive checkpoints produce no evidence, stop that lane and self-check: the goal contract, scope, dependency, ownership, test method, and blocker. Resume only with a safe correction or an explicitly requested user decision. Status prose, repeated waits, and unverified claims are not evidence.

Use `/goal` only when the goal is confirmed, acceptance is testable, and there is no pending human gate.

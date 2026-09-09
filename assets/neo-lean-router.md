<!-- neo-lean-router:start -->
## Neo Lean Router (Neo 8GB private branch)

Apply this routing contract before Chief initialization or delegation. It scopes the Chief rules below and overrides this repository's broader defaults for concurrency, retries and follow-up. It never overrides user instructions, permission boundaries, safety checks, or required visual selection.

### Select the execution level

Default to DIRECT: one concrete outcome, one primary write surface, existing source build/package/install/run, local fixes, configuration, content edits, or a known implementation. Work as one agent; no durable roles, subagents, Chief state initialization, or product discovery.

Use LEAN for tightly coupled multi-file implementation, ordinary debugging requiring investigation, focused review, or bounded refactoring. LEAN uses one writer and at most one optional read-only verifier, only when independent evidence will materially help. The verifier cannot delegate, mutate any surface, or run concurrently with a heavy build. File count, producing an artifact, a deadline, or one unresolved question alone does not justify CHIEF.

Use CHIEF when the user explicitly requests Chief/team governance for this task, or at least TWO distinct, evidence-backed complexity signals apply:

1. Multiple independent workstreams need coordination.
2. Multiple durable specialist roles are needed.
3. Material product or architecture decisions remain unresolved.
4. Delivery needs coordinated ownership across product, engineering, design, testing, or operations.
5. Work is expected to span multiple sessions with durable coordination.
6. Substantial approval, dependency, or ownership routing is required.

Do not count the same fact twice. A mention of Chief as the repository being edited is not a request to invoke Chief. When uncertain choose the lower level, then reassess only on concrete scope/dependency evidence. On upgrade retain the goal, evidence, acceptance criteria, permissions, and consumed retry budget. A registered task inside an active Chief project retains its parent's contract and gates; routing never detaches it to bypass them.

Existing-source build/package/run/install and ordinary debugging are exempt from NEW product discovery. In DIRECT/LEAN do not initialize Chief just to record the exemption. For an explicitly requested Chief doing only already-decided operational commands, record a reasoned `coordination_only` classification and use coordination work, not production roles. A substantive code change within an already-governed deliverable project uses its existing approved discovery evidence; if missing or the product boundary changes, retain the Chief discovery gate. Creating a new product or changing material requirements is not ordinary debugging.

### Default execution discipline (no companion invocation needed)

- Establish the goal, evidence, allowed write surface, constraints and acceptance checks once. Reuse verified context; search with `rg` first, read relevant ranges, and expand only for a concrete dependency or unresolved acceptance question. Reuse existing scripts, tools and tests. Keep output bounded and one proportional plan; update it only for material changes.
- Information Gain Gate: before another search, retry, tool call, review, or delegation, identify the unresolved question, expected new evidence and how alternative results change the next action. If it cannot change a decision or fulfill a required acceptance check, omit it. Repeating unchanged evidence is not progress.
- Same-class failure retry budget = 2 retries after the initial failed attempt (at most three attempts total). Each retry requires new causal evidence or a changed corrective action passing the Information Gain Gate. After exhaustion stop that failing action; a bounded read-only diagnosis or distinct safe path may continue, but a renamed phase, new agent, new log or a deadline never resets this budget. Preserve failure history; respect any stricter/consumed limit. Full Chief repair allowances cannot increase this Neo ceiling.
- Acceptance-met hard stop: once every requested deliverable and required check is satisfied, report the evidence and stop execution. No speculative polish, unrelated refactoring, extra review rounds or new phases. A required final human acceptance remains pending; do not claim it was granted or use it to keep polishing.
- Until acceptance is met, preserve `auto_advance_low_impact=true`: execute the strongest safe authorized in-scope next step. Set `proactive_follow_up=false`: no unsolicited wakeups, recurring scans, reminders or background follow-up. Existing explicitly authorized automations are not modified; new scheduling needs its own user request.

### Neo resource ceiling, including CHIEF

At most ONE active phase lane and ONE active writer across the task, even on disjoint files. Serialize build/debug/test work; no concurrent heavy builds, emulators or verifier during a heavy build. DIRECT has no subagents; LEAN has at most the one read-only verifier above. CHIEF retains durable specialists, discovery, governance, approvals and stronger review when warranted, but schedules production writers sequentially and pauses other compute-heavy work during builds. Discovery evidence lanes are logical categories, not permission for parallel processes. These ceilings also constrain Agent OS, capability scans and temporary meeting helpers. Historical custom state is not rewritten automatically; its larger limits cannot authorize extra Neo concurrency.

Only CHIEF loads the full Chief workflow. DIRECT/LEAN finish locally without creating a governance hierarchy. Full Chief capabilities remain available on upgrade under these Neo execution ceilings.
<!-- neo-lean-router:end -->

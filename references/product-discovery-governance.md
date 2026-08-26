# Product discovery governance

Apply this gate to every Chief-managed project after the initial mission and goal boundary are confirmed and before production execution begins.

## Classification

- `deliverable_project`: creates or materially changes a product, service, codebase, design, content asset, or another acceptance-tested deliverable. Product discovery is mandatory.
- `coordination_only`: limited to synchronizing or pushing already-decided changes, meeting summaries, filing or process follow-up, and read-only audit or aggregation. Record a concrete exemption reason.

Do not infer the classification during initialization. Store it in `.chief-of-staff/product-discovery.json` after goal confirmation. If coordination scope expands into product creation or substantive delivery, immediately reclassify it as `deliverable_project`; the prior exemption no longer authorizes another phase or role.

## Required sequence

`Chief initialization → goal-boundary confirmation → classification → Product Manager and discovery gate when required → production execution`

Before classification or while a deliverable gate is incomplete, permit only goal clarification, read-only discovery, requirements work, and reversible planning. Immediately before creating or starting engineering, design, content production, or another production-execution phase or role, run:

```bash
python3 scripts/init_project.py --target <project-root> --check
```

A nonzero result is a hard stop. Continuation policy selects the strongest safe discovery path but cannot convert a pending gate into production authorization.

## Product Manager phase lead

The Product Manager is one depth-2 phase lead under the project Chief. It is not a Chief, does not become a second user-facing control plane, and does not own central project state. The Chief remains the sole writer of the project plan, task registry, approval queue, and consolidated status.

The Product Manager manages four bounded evidence lanes:

1. `project_initiation`: problem definition, goals and non-goals, success and acceptance measures, and a go/conditional-go/no-go recommendation.
2. `requirements_analysis`: a traceable multi-source demand inventory; core needs, secondary improvements, and long-range ideas; and evidence for rejecting false, duplicate, or impractically difficult requests.
3. `market_research`: competitors, market context, user segments and pain points, policy constraints, business model, acquisition channels, costs, expected value, and material evidence gaps.
4. `architecture_feasibility`: non-binding feasibility, system constraints, interfaces, dependencies, and risk. The later Technical Lead retains final engineering-architecture authority.

With subagents available, each lane uses one depth-3 temporary helper with `delegation_allowed: false`; helpers cannot delegate again or create durable roles. When the runtime lacks subagents, the Product Manager may use `pm_single_task_fallback`, must record the runtime limitation, and must still produce separate artifacts and evidence for all four lanes.

## Required synthesis

The gate cannot pass until the evidence-backed synthesis includes:

- project charter, problem definition, goals, non-goals, acceptance metrics, and initiation recommendation;
- market and competitor research, user pain points and personas, policy constraints, and business feasibility;
- requirements inventory and prioritization, including rejection evidence for false, duplicate, or exceptionally difficult demands;
- advisory architecture feasibility and constraints;
- risks, evidence gaps, recommended MVP or phase scope, and a traceable evidence index.

Every material entry is a `verified_fact`, `assumption`, or `open_question`. A verified fact requires a traceable source, verification method, and verification time; assumptions and open questions stay explicitly unverified. Lane and deliverable evidence refs resolve to evidence-index IDs, and every lane/deliverable needs at least one verified-fact ref before passage. Local artifact/source refs use `repo://` paths that exist inside the project root. The fixed synthesis-coverage map must affirm every required topic before passage. Never invent an interview, survey, market figure, policy finding, user quote, or metric baseline. Human outreach, survey delivery, paid data, restricted access, and any protected action require their own authorization before execution.

## Review and boundaries

Under `exception_only`, the project Chief reviews ordinary Product Manager and helper evidence. Escalate only a material unresolved product direction, visual choice, protected action, safety or permission issue, ownership conflict, failed or unverifiable acceptance, or final project completion. Under chair-led governance, use the established general-office and Creative Director routes.

The Product Manager may record experience goals and visual questions. Clickable NON-FINAL visual options still go only to the configured Creative Director; product discovery never approves or finalizes them.

Gate passage does not authorize deletion, production changes, release, payment, external messages, permission expansion, or another separately protected action.

## Legacy projects

When an older project lacks product-discovery state, migrate it to `legacy_unclassified` and `legacy_pending`. Preserve its existing task and phase IDs in the migration allowlist, anchor that snapshot with the immutable digest in `project.json`, and mark only those records `legacy_existing`. They may finish already-running non-high-impact work. Any later allowlist expansion or new record that claims legacy status fails validation. Before the next production phase, classify the project and complete either the coordination exemption or the deliverable gate; never infer `passed` or `exempt` during migration.

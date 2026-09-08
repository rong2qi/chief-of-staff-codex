---
name: agent-orchestration
description: Route complex engineering work among Codex agents with bounded deliberation, a single implementation writer, and independent verification. Use when work needs explicit multi-agent routing, model roles, or retry limits; do not use for straightforward single-agent tasks.
metadata:
  short-description: Bounded multi-agent routing
---

# Agent Orchestration

Turn a request into one bounded execution contract and choose the smallest route that can satisfy it. Read [the profile schema](references/profile-schema.md) before using a profile. Apply `agent-profiles/config.toml` when it exists. Profiles are decision aids: invoke only agents and models actually available in the current runtime.

## Contract

Capture goal, evidence, scope/non-scope, risk, acceptance checks, protected write surfaces, and user-selected model or budget.

## Route

- **Single agent:** clear, low-risk work with one write surface; run one relevant check.
- **Scout → implementer → verifier:** uncertain medium-risk or cross-file work. Scout and verifier are read-only; implementer is the sole writer.
- **Arbiter → implementer → independent review:** security, data, migration, release, public-interface, or unresolved-design work. Stop for human authorization before irreversible external action.

Use at most three active stages. Do not fan out work with a shared write surface or duplicate investigations.

## Bounded deliberation and repair

- Apply each profile's `max_turns` only to substantive role turns.
- Limit proposal/objection exchanges to two decision rounds. If unresolved, report alternatives, evidence, and the decision needed.
- The initial independent verification does not consume a repair cycle. A concrete defect permits up to three focused repair-and-independent-recheck cycles under the current user rule; retain evidence each time. Legacy limits remain unchanged. With enabled autonomy policy, a genuine covered phase may start a fresh phase-local allowance and narrowly supersede recorded numerical local-preparation limits; a label change cannot reset it, and permission/safety/denial/paused/real-data/production/external stops still prevail.
- When a limit is exhausted, stop; never silently broaden scope or loop.

## Handoff and constraints

Each stage receives the contract, prior evidence, owned write surface, deliverable, acceptance check, and prohibited changes. It returns facts, inference, open questions, evidence, and no unowned modifications.

Preserve user-selected models. Otherwise use Luna for read-only checks, Terra for normal implementation, and Sol for high-risk arbitration. When the routing convention is explicitly enabled and the problem has a complex causal chain, cross-module conflict, or acceptance-boundary dispute, use Astra for the initial synthesis, Terra as the sole writer, then Sol as an independent high-risk review. Astra is not a new permanent Chief layer.

Read [the profile schema](references/profile-schema.md) before using its Astra candidate convention. It is not a Codex-native runtime configuration: `enabled = true` only permits a recommendation after runtime availability is confirmed. If Astra is unavailable, state the Sol downgrade; do not silently substitute it. A user-selected model wins. No independent safety review means no PASS.

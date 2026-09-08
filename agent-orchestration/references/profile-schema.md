# Agent profile schema

Profiles in `agent-profiles/` are conventions interpreted by the accompanying skill, not native Codex configuration keys.

```toml
model = "gpt-5.6-luna"
reasoning_effort = "low"
max_turns = 1
write_access = false
task_types = ["search"]
```

The routing budget is in `agent-profiles/config.toml`. User instructions override profiles; stricter runtime limits override both.

## Astra candidate convention

`schema_version = 2` may define `enabled`, `default_active_agents`, `max_active_agents`, `max_parallel_business_lanes`, `max_heavy_local_tasks`, and exact model identifiers under `[models]`. These are conventions interpreted by the routing skill; they are not native Codex configuration keys and do not create agents, reserve slots, or switch a runtime.

When `enabled` is absent or `false`, retain the legacy routes. When it is `true`, it must be a real boolean and the models must be exactly `gpt-6-astra`, `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`. The candidate default is three active slots including the primary agent. A fourth slot needs both confirmed runtime capacity and a specific independent benefit; at most two business lanes and one local heavy workload may run at once. Shared Git index operations remain the sole integrator's responsibility.

Use `astra-arbiter` at medium effort for complex synthesis (high only for a genuinely complex causal chain), `terra-implementer` at medium effort as the single writer, `sol-arbiter` at high effort for independent safety/financial/identity/migration/release review, and `luna-scout` at low effort for read-only evidence. Pause, permission, safety, denial, real-data, production, and external-action contracts are never reset. Legacy numerical limits remain unchanged; enabled autonomy may renew only a genuine phase-local allowance under its recorded numerical local-preparation exception and approved plan binding.

# Astra routing convention / Astra 路由约定

This is a reviewable candidate, not Codex-native runtime configuration. `enabled = true` permits only a validated recommendation; it neither creates agents nor switches a runtime. Missing or `false` enablement keeps legacy routes. Invalid enabled configuration blocks routing and generation rather than silently falling back.

Use Astra at medium effort for complex synthesis (high only for complex causal chains), Terra at medium effort as the sole writer, and Sol at high effort as the independent safety, financial, identity, migration, or release reviewer. An explicit user model changes only the implementation role: high risk still requires a different-agent Sol review and is never a PASS by itself. Astra unavailability is an explicit Sol downgrade.

Default capacity includes the primary agent plus up to two active slots. One slot blocks a multi-agent path with `capacity_shortfall`; two or three slots may run stages serially. A fourth slot needs both observed capacity and a concrete independent benefit. Limit work to two business lanes and one local heavy workload; the sole integrator owns the shared Git index.

The `astra_routing.py` utility only validates, routes, or renders stdout. Its strict prospective global transform preserves non-target bytes, replaces only the unique exact legacy routing section, and updates the one bullet in the unique triage section. The Testing Chief is mandatory for presentation; if its interface is unavailable, related enablement or presentation is blocked.

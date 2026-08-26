# Optional operator preferences

Chief of Staff has a neutral public core. Personal interaction rules apply only
when an operator explicitly enables them in a validated preference profile.
Installing or cloning the Skill never executes setup by itself.

## First-use routing

Enter onboarding only after an explicit request such as `配置 Chief of Staff`,
`重新配置个人偏好`, or project initialization when no profile exists.

When the host exposes a blocking selection UI, ask these three questions in one
panel:

1. Preset: `core`, `operator-controlled-bilingual`, or `custom`.
2. Salutation: neutral, `妈妈`, or a custom value.
3. Data placement: default personal Codex data directory, an external absolute
   path, or the current project only.

Put the following guidance in the preset help text instead of hiding it in later
documentation:

- **Enterprise or mature team:** full Chief coordination is recommended when
  ownership boundaries, approvals, independent verification, and evidence
  trails justify the additional token cost. Start from neutral preferences and
  set concurrency, model routing, phase budgets, and stopping conditions for the
  project.
- **Individual or beginner:** use Chief selectively. Recommend `core`, one
  phase, one writer, and lower-cost model routing. Offer this repository's
  original explicit-only `$kai-lean-execution` as an optional companion when
  separately installed, but never invoke it automatically or inject subagents
  from onboarding.
- `operator-controlled-bilingual` is a personalization preset, not a token-saving
  preset. `custom` is for operators who want to decide each policy separately.

Show the resolved profile, destination, and fallback behavior before asking for
one final Apply / Revise / Cancel decision. If the host lacks a selection UI,
ask the same questions conversationally. A cancelled setup writes nothing. A
saved profile prevents repeated onboarding; an explicit reconfigure request may
replace the managed values later.

The deterministic fallback is:

```bash
python3 scripts/configure_preferences.py \
  --preset operator-controlled-bilingual \
  --scope global \
  --salutation 妈妈 \
  --voice Samantha \
  --data-root /absolute/path/to/chief-data
```

## Schema and behavior

- `pin_governance`: global policy for scarce Chief pin slots. Its enabled form
  registers exactly one `general_office`, `todo`, `creative_director`, and
  `context_migration_monitor`, each with a non-empty exact thread ID. Public
  presets are disabled and use generic titles with `thread_id: null`.
- `pin_governance.optional_chief_slots`: defaults to limit `6`, ordinary
  `default_pin_primary_task: false`, `recommend_then_operator_approve`, manual
  non-Chief pin protection, and `observed_capacity_then_paired_replacement`.
- `pin_governance.recommendation_policy`: the general office may form at most
  one pending pack with three candidates. TODO is a read-only verifier of
  identity, currentness, duplication, evidence freshness, capacity, and lineage.
  Paused/completed/superseded/migration-cancelled and routine push, meeting,
  report-only, or process-only Chiefs are excluded by default.
- `pin_governance.successor_inheritance`: requires an exact fresh
  `pinnedThreads` check before takeover; a `pinned:true` receipt is not proof.
  Only mandatory or explicitly approved lineages can create one same-lineage
  replacement after a safe `MIGRATION_READY` handoff.
- `grandmothered_optional_chiefs`, `protected_manual_thread_ids`, and
  `invalid_successor_thread_ids` are private live-state lists. Public examples
  keep them empty and never publish real task IDs.

Pre-matriarchal profiles are normalized through one compatibility shim. A
legacy-only list is moved to `grandmothered_optional_chiefs`; a transition
profile containing both aliases is accepted only when their values are exactly
equal. Any mismatch fails closed. Persisted output contains only the current
field, so repeated migration is idempotent.

- `report_review_mode`: `exception_only` lets the project Chief review routine
  child handoffs and escalates only enumerated exceptions plus final project
  completion. `all_reports` restores operator review for every milestone/final
  handoff.
- `governance_model.enabled`: enables `chair_led_cabinet`; the operator becomes
  the chair, project Chiefs own routine administration, auditors are evidence-only,
  non-visual exceptions route through the configured general office, and only the
  general office plus Creative Director are authoritative TODO sources.
- `governance_model.continuation_policy.enabled`: requires project Chiefs to
  execute the strongest evidence-backed safe in-scope continuation. Stopping,
  preserving a failed state, and delaying remain operator-initiated choices while
  such a path exists. Only a continuation that itself needs a new permission or
  a new Chief is escalated; all protected-action and safety boundaries remain.
- `visual_selection_gate.enabled`: require clickable, non-final previews and an
  explicit operator choice before final visual implementation. `review_hub_title`
  identifies the one operator-facing Creative Director task; project Chiefs must
  not duplicate the same visual request to the general Chief task or TODO.
- `american_english_coaching.enabled`: add the requested written, spoken, and
  idiom sections. `include_casual_chat` controls whether ordinary conversation
  is included.
- `audio_playback.enabled`: render only the clip kinds listed in `clips`.
  With `provider: host_builtin`, keep the English text available to the host's
  built-in voice/read-aloud control and generate no files. A Skill must not claim
  that it can trigger autoplay or a per-sentence native player unless the host
  exposes that capability. With `provider: auto` or `macos_say`, `storage_root`
  must already exist when rendering; an unavailable root produces text only and
  never falls back to another directory.
- `operator_salutation.enabled`: use `value` as the operator's preferred form of
  address.
- `paused_title_prefix.enabled`: reflect explicit pause and resume decisions in
  the Chief title using `value`.
- `reminders.enabled`: use the embedded schedule with the existing unanswered-
  Chief reminder workflow. Saving a preference does not itself create an
  automation; automation creation still follows the reminder workflow.

Preserve unknown top-level fields when reconfiguring an existing valid profile.
Never publish a live profile, generated audio, task identifiers, credentials,
server addresses, or private storage paths.

## Voice delivery

`host_builtin` is the recommended default for operators who already use the
Codex/ChatGPT app's built-in voice experience. It stores no generated audio and
does not call the offline renderer. The host controls playback, voice choice,
and whether read-aloud is available.

`scripts/render_english_audio.py` is an opt-in offline attachment renderer. It
creates one content-addressed `.m4a` for a single enabled `written` or `spoken`
sentence only for the `auto` and `macos_say` providers; `host_builtin` never
calls it or creates a file. On macOS the `auto` provider uses `say`;
a configured voice such as `Samantha` is used only when it is available. Other
platforms or missing tools return a machine-readable
`text_only` result.

After a successful render, embed each returned absolute path as an individual
audio attachment. Do not combine written and spoken clips when both are enabled.

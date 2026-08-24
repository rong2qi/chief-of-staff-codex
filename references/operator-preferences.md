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
  phase, one writer, and lower-cost model routing. Offer the audited explicit-only
  `$lean-code-path` Skill derived from [Ponytail](https://github.com/DietrichGebert/ponytail) as an optional companion when available, but never install or enable it
  from onboarding without a separate explicit decision.
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

- `visual_selection_gate.enabled`: require clickable, non-final previews and an
  explicit operator choice before final visual implementation.
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

`scripts/render_english_audio.py` creates one content-addressed `.m4a` for a
single `written` or `spoken` sentence only for the `auto` and `macos_say`
providers. On macOS the `auto` provider uses `say`;
a configured voice such as `Samantha` is used only when it is available. Other
platforms or missing tools return a machine-readable
`text_only` result.

After a successful render, embed each returned absolute path as an individual
audio attachment. Do not combine written and spoken clips when both are enabled.

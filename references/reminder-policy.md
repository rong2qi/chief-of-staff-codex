# Unanswered-Chief reminder policy

This is a personal cross-project policy. Store the live configuration at `~/.codex/chief-of-staff/reminders.json`; do not copy it into each project.

## Schema

```json
{
  "schema_version": 1,
  "enabled": true,
  "timezone": "Asia/Shanghai",
  "daytime_window": {
    "start": "09:00",
    "end": "18:00",
    "interval_minutes": 60,
    "include_start": true,
    "include_end": true
  },
  "additional_times": ["22:00"],
  "todo_thread_title": "TODO｜待回复 Chief 汇总",
  "todo_thread_id": null,
  "automation_name": "Chief 待回复提醒",
  "automation_ids": []
}
```

Preserve unknown fields. Times use 24-hour `HH:MM`; the interval is a positive integer. Generate occurrences from the start through the end, honoring both boundary flags, then union and deduplicate `additional_times`.

## Enable or update

1. Read the current policy and inspect recorded automations before creating anything. Reuse the TODO thread and automation IDs when valid; search by exact name before replacing a missing ID.
2. Create at most one projectless TODO thread titled exactly `todo_thread_title`, pin it, and store its thread ID. The thread scans every Codex task whose title starts with `Chief of `, subject to the visual-routing rule below.
3. A TODO item exists only when the latest unresolved Chief request explicitly needs user approval, confirmation, a product decision, additional information, or a safety, access, or permission choice. Under `exception_only`, ignore `CHIEF_REVIEW_READY` and legacy child `REVIEW_REQUIRED` markers unless the project Chief classifies an exact exception and emits `USER_ACTION_REQUIRED`. Valid report exceptions are goal confirmation, material product choice, visual choice, protected action, safety/security, scope or ownership conflict, failed or unverifiable work, depth expansion, and final project completion. Chiefs record `USER_ACTION_RESOLVED: <request_id>` after a resolving reply; continue recognizing legacy unmarked non-report requests. Ordinary progress and autonomous work are excluded. Reading a thread is not a reply. When the request is a visual selection governed by the optional visual gate, only `Chief of Creative Direction｜创意总监` is authoritative. Exclude copies or related waiting markers in the source Chief, child roles, `一人之下`, and retired review hubs.
4. Use thread heartbeat automations targeting the TODO thread. Compile the schedule in the requested timezone. When the host timezone already matches, use local wall-clock recurrence. When it does not, use the runtime's timezone-aware or suggested-create flow rather than silently shifting hours.
5. Use the minimum schedule set. One recurrence can combine times sharing the same minute; use separate automations only when the runtime cannot express the exact union without generating extra times. Never create duplicate reminders.
6. Keep ordinary notifications enabled unless the user explicitly asks to mute them. Save confirmed thread and automation IDs back to the policy.

Each run replaces the prior logical snapshot and sorts pending replies by urgency. Each item contains the Chief's exact title, request, request time or latest update, a one-sentence suggested reply, and task ID. Multiple visual decision IDs held by the Creative Director appear under one Creative Director TODO entry rather than as duplicate project entries. Remove resolved, withdrawn, superseded, and completed requests. The TODO task remains read-only.

## Disable

Set `enabled` to `false`, update every recorded reminder automation to `PAUSED`, and verify the paused state. Do not interpret notification muting as disabled: disabled means no scheduled runs. Keep the TODO thread and IDs for reversible re-enablement unless the user explicitly asks to delete them.

## Default schedule

The default policy runs at every Beijing-time hour from 09:00 through 18:00 inclusive, plus 22:00. This is equivalent to a 60-minute daytime interval with both boundaries included and one additional time. The user may change the window, interval, timezone, or additional times at any time.

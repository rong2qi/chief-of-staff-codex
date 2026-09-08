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
3. A TODO item exists only when `operator_actionable_now=true` on the latest unresolved request in the authoritative general-office or Creative Director hub. Under `exception_only`, ignore `CHIEF_REVIEW_READY` and legacy child `REVIEW_REQUIRED` markers unless the project Chief classifies an exact exception and emits `USER_ACTION_REQUIRED`. Exclude delegated/resolved records, evidence gathering, unavailable or non-clickable entries, routine reports, ordinary failures, internal retries, ordinary test results, and non-authoritative copies. Chiefs record `USER_ACTION_RESOLVED: <request_id>` after a resolving reply; reading a thread is not a reply. For visual selection, only `Chief of Creative Direction｜创意总监` is authoritative, and the item becomes actionable only after the clickable entry is available, the candidate hash is frozen, and Testing has passed that exact candidate. Exclude related waiting markers in source Chiefs, child roles, `一人之下`, and retired hubs.

With the explicitly enabled approved-decision-relay policy, TODO may make one direct, literal delivery of an already-approved nonvisual decision to its unique registered current source Chief after checking the stable ID and original words. General Office receives the same immutable audit record asynchronously and does not serialize the delivery. Delivery, ACK, or audit is not execution, a new approval, or Testing evidence; unknown, stale, duplicate, and failed deliveries are recorded and never blindly resent or rerouted. Without that opt-in, TODO remains relay-free. In both modes, missing package evidence, preparation, and evidence collection stay Chief-owned until an exact reserved decision is identified.
4. Use thread heartbeat automations targeting the TODO thread. Compile the schedule in the requested timezone. When the host timezone already matches, use local wall-clock recurrence. When it does not, use the runtime's timezone-aware or suggested-create flow rather than silently shifting hours.
5. Use the minimum schedule set. One recurrence can combine times sharing the same minute; use separate automations only when the runtime cannot express the exact union without generating extra times. Never create duplicate reminders.
6. Keep ordinary notifications enabled unless the user explicitly asks to mute them. Save confirmed thread and automation IDs back to the policy.

## Successor inheritance

Before a reminder target task's successor takes over, becomes the authoritative entry, or the predecessor is archived, inventory every bound reminder automation with exact ID, name, kind, target task ID, status, schedule, prompt SHA-256, and notification policy. Reuse the existing automation and rebind its exact target to the successor. Only when a fresh live view proves the old automation is absent, and creation remains inside the existing user authorization, create exactly one minimal equivalent.

Re-read the live automation view and verify the exact successor target, status, schedule, prompt hash, and notification policy. A saved policy/configuration reference or create/update receipt is not proof. Two ACTIVE automations with the same reminder duty are forbidden. Any missing, duplicate, or mismatched binding records `automation_rebind_failed`, returns `MIGRATION_BLOCKED`, and keeps the predecessor active and unarchived. Bundle parity, automation parity, and applicable pin parity must all pass before takeover. Historical repair never unarchives or deletes the predecessor and never creates a duplicate task or reminder.

Each run replaces the prior logical snapshot and sorts pending replies by urgency. Each item contains the Chief's exact title, request, request time or latest update, a one-sentence suggested reply, and task ID. Multiple visual decision IDs held by the Creative Director appear under one Creative Director TODO entry rather than as duplicate project entries. Remove resolved, withdrawn, superseded, and completed requests. The TODO task remains read-only.

## Disable

Set `enabled` to `false`, update every recorded reminder automation to `PAUSED`, and verify the paused state. Do not interpret notification muting as disabled: disabled means no scheduled runs. Keep the TODO thread and IDs for reversible re-enablement unless the user explicitly asks to delete them.

## Default schedule

The default policy runs at every Beijing-time hour from 09:00 through 18:00 inclusive, plus 22:00. This is equivalent to a 60-minute daytime interval with both boundaries included and one additional time. The user may change the window, interval, timezone, or additional times at any time.

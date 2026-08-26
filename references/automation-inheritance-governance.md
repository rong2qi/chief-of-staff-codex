# Automation inheritance governance

Task-bound automations are part of migration continuity, not disposable configuration. A migration bundle inventories every binding with exact `id`, `name`, `kind`, `target_thread_id`, `status`, `schedule`, `prompt_sha256`, and `notification_policy`.

Before takeover, authority switching, or predecessor archival:

1. Inspect the live automation view and reuse each existing automation by rebinding its exact target to the successor task ID.
2. Preserve schedule, prompt semantics and SHA-256, notification policy, status, and scope. Same duty is the canonical tuple of name, kind, canonical-JSON schedule, prompt SHA-256, and notification policy; target and runtime ID are excluded. Never leave two ACTIVE automations with the same duty fingerprint; intentional different schedules are distinct duties.
3. Only when live evidence proves the old automation no longer exists, and creation remains inside existing user authorization, create exactly one minimal equivalent. A missing automation does not broaden permission.
4. Re-read the live automation view. A bundle reference, configuration reference, or update/create receipt is not proof. Verify exact target, ACTIVE status when expected, schedule, prompt hash, and notification policy.
5. Require bundle parity, automation parity, and pin parity when the lineage is pin-eligible. Any missing, duplicate, target/status/schedule/hash/notification mismatch, or absent live evidence returns `MIGRATION_BLOCKED`, records `automation_rebind_failed`, and keeps the predecessor active and unarchived.

For a predecessor already archived before this rule, repair only the live automation binding. Do not unarchive or delete the predecessor, create a duplicate task, or create more than one equivalent automation.

The public `automation_inheritance` preference is disabled and anonymous by default. Enabling it does not itself authorize automation creation or mutation; it activates this validation contract only where the operator already authorized the automation workflow.

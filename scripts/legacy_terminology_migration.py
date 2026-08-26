#!/usr/bin/env python3
"""One-way compatibility shim for pre-matriarchal Chief pin terminology.

Legacy spellings are accepted only as persisted input. Every returned object uses
the current terminology, and conflicting dual-key profile input fails closed.
"""

from __future__ import annotations

import copy
from typing import Any


LEGACY_PROFILE_KEY = "grandfathered_optional_chiefs"
CURRENT_PROFILE_KEY = "grandmothered_optional_chiefs"
LEGACY_ROLE_CLASS = "grandfathered_optional_chief"
CURRENT_ROLE_CLASS = "grandmothered_optional_chief"
LEGACY_AUTHORIZATION_STATUS = "grandfathered_pending_review"
CURRENT_AUTHORIZATION_STATUS = "grandmothered_pending_review"
LEGACY_PIN_STATUS = "grandfathered_preserved"
CURRENT_PIN_STATUS = "grandmothered_preserved"
LEGACY_SNAPSHOT_PIN_CLASS = "grandfathered_optional"
CURRENT_SNAPSHOT_PIN_CLASS = "grandmothered_optional"


class LegacyTerminologyConflict(ValueError):
    """Raised when legacy and current aliases disagree."""


def migrate_profile_input(profile: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    migrated = copy.deepcopy(profile)
    pin = migrated.get("pin_governance")
    if not isinstance(pin, dict) or LEGACY_PROFILE_KEY not in pin:
        return migrated, False
    legacy_value = pin[LEGACY_PROFILE_KEY]
    if CURRENT_PROFILE_KEY in pin and pin[CURRENT_PROFILE_KEY] != legacy_value:
        raise LegacyTerminologyConflict(
            "legacy and current pin-governance aliases disagree"
        )
    pin[CURRENT_PROFILE_KEY] = legacy_value
    del pin[LEGACY_PROFILE_KEY]
    return migrated, True


def migrate_pin_state_input(state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    migrated = copy.deepcopy(state)
    changed = False
    replacements = {
        "role_class": (LEGACY_ROLE_CLASS, CURRENT_ROLE_CLASS),
        "authorization_status": (
            LEGACY_AUTHORIZATION_STATUS,
            CURRENT_AUTHORIZATION_STATUS,
        ),
        "pin_status": (LEGACY_PIN_STATUS, CURRENT_PIN_STATUS),
    }
    for key, (legacy_value, current_value) in replacements.items():
        if migrated.get(key) == legacy_value:
            migrated[key] = current_value
            changed = True
    return migrated, changed


def migrate_pin_snapshot_input(snapshot: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    migrated = copy.deepcopy(snapshot)
    changed = False
    pinned = migrated.get("pinned_threads")
    if isinstance(pinned, list):
        for item in pinned:
            if isinstance(item, dict) and item.get("pin_class") == LEGACY_SNAPSHOT_PIN_CLASS:
                item["pin_class"] = CURRENT_SNAPSHOT_PIN_CLASS
                changed = True
    return migrated, changed

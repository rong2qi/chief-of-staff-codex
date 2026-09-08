"""Synthetic host-private authority fixture for tests only."""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import tempfile
from pathlib import Path


TESTING_REVIEWER_ID = "testing-reviewer-synthetic-1"
_temporary = tempfile.TemporaryDirectory(prefix="chief-private-authority-")
_config = Path(_temporary.name) / "authority.json"
_raw = (json.dumps({
    "schema": "CHIEF_PRIVATE_AUTHORITY_CONFIG_V1",
    "testing_reviewer_task_id": TESTING_REVIEWER_ID,
}, sort_keys=True, separators=(",", ":")) + "\n").encode()
_config.write_bytes(_raw)
os.environ["CHIEF_PRIVATE_AUTHORITY_CONFIG_PATH"] = str(_config)
os.environ["CHIEF_PRIVATE_AUTHORITY_CONFIG_SHA256"] = hashlib.sha256(_raw).hexdigest()
atexit.register(_temporary.cleanup)

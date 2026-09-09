# Explicit build execution protocol

Use `scripts/build_execution.py:execute_build` for a single admitted build attempt. This is a callable standard-library helper, not an automatic process scheduler or a command execution CLI. It never changes machine-wide settings, starts real builds on its own, signs, installs, publishes, or grants release authorization.

## Order and evidence

1. Create a unique repository-local `artifacts/quarantine/build-*` attempt with a `NOT_FOR_PRODUCTION` marker and report. Snapshot every declared prior artifact before any callback can overwrite it. If preservation fails, stop before expensive execution.
2. Require a nonempty source revision, an explicit output mode, cheap prechecks, and the applicable required validator adapters. Missing or unknown facts fail closed. Run cheap static/configuration checks before admission and build.
3. Call the zero-argument `admit_work` adapter immediately before expensive execution. Only literal `True` admits work. The integration owner must atomically enforce the current work's cumulative budget, unique writer, resource capacity, and diagnostic gates. Unknown capacity permits at most one heavy task; independent light work may continue. Release a claimed resource in the caller's `finally` block. This helper neither stores work state nor substitutes for admission governance.
4. Pass a mapping of fresh output paths to the build adapter. `apk-only` provides only `apk`; `apk-and-aab` provides both. The adapter must write those exact paths, complete synchronously, and return literal `True` only for successful execution. Fresh paths prevent stale prior files being mistaken for new output.
5. Preserve every generated declared file before any postcheck, even when build execution fails, raises, or is interrupted. Raw staging files are also retained. Snapshot records carry original path, preserved path, byte size, and SHA-256. A missing/empty output is an explicit failed necessary gate; an empty file is still retained.
6. Run existence/nonempty checks and explicit `parse`, `package`, `version`, and `certificate` adapters for each applicable kind. Each receives a separate copy. Adapters must perform the real platform checks and compare actual metadata with the intended package, version, and certificate policy. This helper does not parse APKs or prove signatures itself. APK-only never invokes AAB validators.
7. Optional noncritical checks receive disposable copies after preservation. Their failure produces a warning and cannot delete the preserved APK. Required validation/signature failure blocks eligibility while retaining the bytes and `NOT_FOR_PRODUCTION` marker.

## Result and integration contract

`execute_build(repository=..., source_revision=..., mode=..., prechecks={name: callback}, admit_work=callback, build=callback, validators={kind: {name: callback}}, prior_outputs=[...], noncritical_checks={name: callback})` returns a JSON-serializable report and writes the same report to the attempt directory. Pass an existing repository directory. Prior paths must identify existing regular files; do not pass nonexistent expected outputs as prior artifacts.

Report `source_revision`, `build_status`, `validation_status`, `release_status`, artifact hashes, individual checks, and errors separately. A successful process is not successful validation. `ELIGIBLE_FOR_REVIEW` means only that supplied checks passed; separate release authority is still required. The conservative `NOT_FOR_PRODUCTION` marker remains even for an eligible candidate because the helper has no production authorization path.

Adapters are trusted in-process code. They must not modify quarantine snapshots, spawn detached work, mutate undeclared outputs, or claim success without checking the intended facts. Passing scratch copies prevents incidental adapter cleanup from deleting snapshots; it is not an adversarial sandbox. Register all outputs and prior files which must survive. The helper cannot discover undeclared output locations, recover bytes lost before it ran, guarantee preservation after force-kill/power loss, or preserve bytes when storage is unavailable. Storage errors stop eligibility; staging/prior files are never deliberately deleted. Ordinary callback exceptions become failed evidence; process-level interruptions propagate after best-effort preservation and reporting. Source revision is caller-supplied provenance, not automatic clean-tree verification.

## Verification

`python3 -m unittest discover -s tests -p test_build_execution.py` uses local byte-writing process doubles, not actual Android tooling. It covers static gating, admission unknown/error, missing validator configuration, both mode boundaries, prior-output preservation, fresh attempts, missing/empty output, partial build failure, process interruption, signature rejection, validator cleanup/error, and noncritical failure. Real package/signing adapter integration remains the caller's responsibility.

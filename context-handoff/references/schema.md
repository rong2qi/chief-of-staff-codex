# Bundle schema

Each lineage has numbered directories containing `manifest.json`, `handoff.md`, `artifacts.json`, and `transcript-ref.json`.

The manifest records schema version, lineage/migration number, status, predecessor/successor IDs, title, cwd/project, model, context sample, source session hash, Git snapshot, global instruction hash and salutation, file checksums, and UTC timestamps. Status is `checkpoint_ready`, `successor_created`, `verified`, or `needs_attention`; never mark verified before handshake parity.

`artifacts.json` is an object of stable file/commit/branch/task/approval/report/link/check references without secrets. `transcript-ref.json` contains only the immutable predecessor session path, hash, size, time, and thread ID.

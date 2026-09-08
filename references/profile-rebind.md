# Profile rebind candidate

`scripts/profile_rebind.py` exposes a no-write preparation interface. It checks
caller-supplied absolute profile and global `AGENTS.md` preimage hashes, rejects
missing, symlinked, hard-linked, or invalid profiles, validates the existing
profile without normalizing it, and runs the existing managed-block generator on
an isolated copy. Its receipt records only hashes and the profile locator. It
does not write a profile or global instructions file; promotion remains a
separately gated installation step.

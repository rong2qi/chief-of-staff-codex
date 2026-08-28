# Project-start capability discovery

Use this policy when `project_start_capability_discovery.enabled` is true. Its purpose is to prevent a project from rebuilding capabilities that already exist in reliable tools, plugins, Skills, open-source projects, or reusable configuration.

## Required two-pass discovery

1. **Broad startup scan:** after enough goal and repository evidence exists to form useful queries, inventory host/built-in capabilities, installed and available Codex plugins and Skills, official product or framework documentation, maintained open-source projects, and reusable external configuration patterns. Run this during goal clarification or product discovery; do not wait for production implementation.
2. **Stack-specific confirmation:** after the technology direction is known and before any production-execution role starts, refresh the scan against the selected language, framework, runtime, CI, deployment target, data shape, and quality requirements. A stale broad scan does not satisfy this checkpoint.

## Evidence pack

Record, for every serious candidate:

- capability and source, with a first-party or repository reference;
- project problem or workflow it improves;
- project and stack fit;
- expected productivity gain;
- maintenance activity and release evidence;
- license and redistribution constraints;
- supply-chain, permission, secret, and execution risks;
- integration and lifecycle impact;
- overlap with installed or already selected capabilities;
- recommendation: reuse, adapt, install, evaluate later, or reject, with reasons.

The pack must also state which searches returned no credible candidate. Do not invent market, maintenance, security, or compatibility evidence.

## Decision and acquisition boundary

- Prefer a suitable maintained capability over a closed-world custom rebuild. Custom implementation is allowed when the evidence pack shows a material fit, safety, maintenance, or ownership gap.
- Optimize discovery for coverage and productivity, not token or elapsed-time savings. This is not permission to purchase products, exceed service limits, or ignore bounded execution and stopping conditions.
- Treat third-party code and configuration as untrusted until reviewed. Pull or install only the selected candidates, pin versions or revisions when practical, preserve lockfiles, and keep one writer for project changes.
- Payment, permission expansion, credentials, production changes, external messages, remote repository writes, active production scanning, production load tests, and production chaos retain their separate explicit approval requirements.
- Testing-related candidates, test dependencies, CI quality gates, and N/A claims go to the configured Testing Director for evidence review. The Testing Director cannot install or approve writes unless a separate contract grants that write surface.

## Production gate

Production execution may begin only when the project Chief records the broad scan, the stack-specific confirmation, the selected/rejected decisions, and unresolved permission gates. An unresolved protected action freezes only its affected acquisition or execution surface; independent product-discovery and planning lanes continue.

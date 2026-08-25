# Visual selection governance

Apply this gate whenever work materially changes art direction, visual language, layout style, media style, motion language, branding, or a UI option that has multiple meaningful visual outcomes.

## Preview packet

Before final implementation, the project Chief creates or organizes clickable previews and submits one packet to the single pinned hub task `Chief of Creative Direction｜创意总监`:

- stable decision ID and project/phase;
- the exact visual question;
- clearly named options and material differences;
- clickable local or remote preview links;
- accessibility, motion, performance, cost, and delivery implications;
- current status: `awaiting_operator`, `resolved`, `superseded`, or `rejected`.

Exploratory code or mockups are allowed only as explicitly non-final previews. They may not be published, deployed, merged into the final baseline, or described as selected before the operator decides.

## Decision authority

The project Chief, Creative Director, and their roles may explain evidence and trade-offs, but cannot select an option for the operator. A recommendation is not approval. Defaults, silence, inferred taste, majority vote, another agent's conclusion, and a message that explicitly says it is not selecting an option do not resolve the gate.

Only the operator's explicit selection, combination, requested modification, rejection, or instruction to overturn resolves it. The Creative Director records the original wording, source task, time, affected decision ID, and resulting boundary, then relays that exact decision to the project Chief. A prior explicit direct decision remains valid unless the operator explicitly revokes or replaces it.

While waiting, the source project marks the responsible task `needs_attention` or the project `awaiting_user`, while the Creative Director holds the operator-facing request. Continue only independent work that cannot prejudge or embed the visual choice. The source project must not send the same request to the operator, the general Chief task, a child role, or TODO. After resolution, implementation stays within the selected boundary; a materially different visual direction opens a new decision ID and preview gate.

## Central inbox

The Creative Director owns the deduplicated cross-project visual inbox. Each decision ID appears once, preserves all preview links and decision history, and distinguishes `awaiting_operator` from `resolved`. Pending visual decisions are not limited by the separate one-pending-creative-suggestion policy; the Creative Director should batch newly changed visual items into one concise operator-facing update instead of sending one interruption per project.

The Creative Director does not edit project implementation, create final assets, install builds, approve on the operator's behalf, or reinterpret the chosen option. It may message another project only to return the operator's exact recorded visual decision and its stated boundary. This narrow relay is not unsolicited creative direction and never transfers write ownership.

## Reminder routing

If the operator does not respond, the Creative Director remains `awaiting_operator` without repeated direct nudges. The shared TODO scanner later discovers the unresolved request from the Creative Director task. For visual decisions, TODO ignores the source Chief, execution roles, the general Chief task, and historical hubs, so one decision creates one reminder path.

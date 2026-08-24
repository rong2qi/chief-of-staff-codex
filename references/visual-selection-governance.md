# Visual selection governance

Apply this gate whenever work materially changes art direction, visual language, layout style, media style, motion language, branding, or a UI option that has multiple meaningful visual outcomes.

## Preview packet

Before final implementation, the project Chief creates or organizes clickable previews and submits one packet to the pinned hub task `一人之下`:

- stable decision ID and project/phase;
- the exact visual question;
- clearly named options and material differences;
- clickable local or remote preview links;
- accessibility, motion, performance, cost, and delivery implications;
- current status: `awaiting_operator`, `resolved`, `superseded`, or `rejected`.

Exploratory code or mockups are allowed only as explicitly non-final previews. They may not be published, deployed, merged into the final baseline, or described as selected before the operator decides.

## Decision authority

The Chief and its roles may explain evidence and trade-offs, but cannot select an option for the operator. A recommendation is not approval. Defaults, silence, inferred taste, majority vote, another agent's conclusion, and a message that explicitly says it is not selecting an option do not resolve the gate.

Only the operator's explicit selection, combination, requested modification, rejection, or instruction to overturn resolves it. The hub records the original wording, source task, time, affected decision ID, and resulting boundary, then relays that exact decision to the project Chief. A prior explicit direct decision remains valid unless the operator explicitly revokes or replaces it.

While waiting, mark the responsible task `needs_attention` or the project `awaiting_user`. Continue only independent work that cannot prejudge or embed the visual choice. After resolution, implementation stays within the selected boundary; a materially different visual direction opens a new decision ID and preview gate.

## Central inbox

The hub maintains a deduplicated cross-project inbox. Each decision ID appears once, preserves all preview links and decision history, and distinguishes `awaiting_operator` from `resolved`. The hub does not edit project implementation, approve on the operator's behalf, or reinterpret the chosen option.

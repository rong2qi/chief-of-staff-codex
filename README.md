# Chief of Staff for Codex / Codex 幕僚长

> 通过一个统一负责的主任务、按职务命名的长期任务，以及临时子代理会议来协调 Codex 项目。
>
> Coordinate a Codex project through one accountable main task, durable role-based tasks, and temporary subagent meetings.

[中文](#中文) · [English](#english)

<a id="中文"></a>

## 中文

[跳转到 English](#english)

### 它能做什么

Chief of Staff 为每个 Codex 项目提供一个统一的用户交互入口。主任务会根据项目名自动命名为 `Chief of <项目名>`，例如 `Chief of 个人web`，并在初始化后自动置顶。你只需要和这个主任务交流；它负责拆解目标、创建需要长期独立上下文的任务、收集结构化汇报，并向你提供最终总结。

每个长期任务可以根据工作内容自动选择已安装的 Skill，也可以召集临时 subagents 完成范围明确的调研、评审、测试或讨论。

### 核心能力

- 每个项目拥有可区分的主任务名称：`Chief of <项目名>`。
- 主任务在初始化完成后自动置顶。
- 子岗位提交里程碑或最终汇报后进入待人工批复状态；Chief 会批量收集同时到达的汇报，避免遗漏。
- Chief 必须先与你确认最终目标、交付物和验收标准；未达成最终验收前持续分阶段推进。
- 默认三层管理结构，阶段负责人可以管理执行岗位；增加第四层前必须申请。
- 用户只与一个统一负责的主任务交互。
- 长期任务统一命名为 `职务｜工作成果`。
- 所有长期子岗位绑定 Chief 所在的同一 Codex 项目；项目尚未保存时默认改用临时 subagents。
- 活动中或待处理的岗位保留在 Recents 便于发现状态；最终汇报获批并登记后自动归档，减少长期堆积。
- 长期任务内部可以召开临时子代理会议。
- Chief 可为同项目岗位建立明确的对接关系；登记过的岗位可以直接交换依赖、接口与证据，并把结论抄送 Chief。
- 每个长期岗位都能按需召集最多三个临时 subagents 开会，由岗位负责人综合结论。
- 默认使用 Luna 进行只读侦察、Terra 作为唯一实施者、Sol 处理高风险裁决。
- 同一文件、外部记录、分支、部署目标或交付物同时只有一个写入者。
- 汇报明确区分已验证事实、推断、待确认项、风险和下一步。
- 删除、生产变更、发布、支付、外发消息和扩大权限前必须取得用户明确授权。
- 使用项目文件保存协调状态，并为未来外置控制平面预留适配接口。
- 默认采用 `effective_throughput`：最多两个互不冲突的阶段并行；每个检查点都要产生可验证证据，连续两个检查点无证据即停止并自查。
- 已确认、可验收且没有人工审批门的目标才可使用 `/goal`；长期目标不会绕过确认或高影响操作的单独审批。
- 创意总监在北京时间每天 11:00 和 20:00 执行有证据的扫描，而非空转目标：只读其他项目、不发消息、不改文件、最多一条待定建议；偏好证据分为 `explicit`、`confirmed_pattern` 和 `hypothesis`。
- 云部署目标和证据登记在独立 deployment registry 中；登记不是授权，生产部署、生产变更、发布或回滚仍须在操作前取得明确用户批准。
- 可选的视觉人工门可要求项目先提供可点击预览，由指定的置顶审阅任务统一收纳；操作者明确选择前，未选方案不得成为最终版本。
- 可选的暂停标题策略会在操作者明确暂停时添加 `已暂停｜`，明确恢复时移除。空闲、阻塞或等待批复不会被误判为暂停。
- 可选的美式英语教学可覆盖工作消息和闲聊，分别提供书面、口语、地道用法及两个独立音频片段。
- 可选启用一个跨项目、置顶的 Chief 待回复 TODO，并按个人策略定时提醒；关闭后完全不运行提醒。

### 环境要求

- 支持 Skills 和 subagents 的新版 Codex 桌面端、Codex CLI 或 IDE 扩展。
- 项目初始化器需要 Python 3.9 或更高版本。

### 安装

克隆本仓库，然后复制或链接到个人 Codex Skills 目录：

```bash
git clone https://github.com/rong2qi/chief-of-staff-codex.git chief-of-staff
cp -R chief-of-staff ~/.codex/skills/chief-of-staff
cp -R chief-of-staff/context-handoff ~/.codex/skills/context-handoff
```

安装后新建一个 Codex 任务。Codex 通常会自动检测 Skill 变化；如果没有出现，请重启 Codex。

### 首次偏好配置

`git clone` 和复制 Skill 本身不会运行任何脚本，也不会立刻弹窗。首次输入以下任一命令时才会开始配置：

```text
$chief-of-staff 配置个人偏好
$chief-of-staff 初始化这个项目
```

如果还没有偏好档案，支持原生阻塞式选择面板的 Codex 客户端会先显示一张三问表单：

1. 预设：`核心 Chief`、`操作者主导 + 双语教学` 或 `自定义`；
2. 称呼：中性、`妈妈` 或自定义；
3. 数据位置：默认个人目录、外置磁盘/自定义绝对路径，或仅当前项目。

Codex 随后展示将启用的规则、写入位置和降级行为，并只在用户选择“应用”后写入。选择“自定义”时，第二张表单可以分别控制视觉确认、闲聊英语教学、书面/口语/地道用法、两类音频、声音与语速、暂停标题、TODO 提醒及其周期。没有原生面板的 CLI 或 IDE 会使用同样问题进行简短对话，不会伪造弹窗。

也可完全跳过交互：

```bash
python3 ~/.codex/skills/chief-of-staff/scripts/configure_preferences.py \
  --preset operator-controlled-bilingual \
  --scope global \
  --salutation 妈妈 \
  --voice Samantha \
  --data-root /Volumes/ExternalDrive/chief-data
```

自定义数据目录必须已经存在；磁盘缺失或权限不足时配置会失败，不会回退写入本机。全局偏好只配置一次，未来项目自动继承；输入 `$chief-of-staff 重新配置个人偏好` 可再次打开向导。公共版默认 `core`，所有个人化规则关闭。

统一配置文件支持以下开关：

- `visual_selection_gate.enabled`
- `american_english_coaching.enabled` 与 `include_casual_chat`
- `audio_playback.enabled`、`clips`、`voice`、`rate` 与 `storage_root`
- `operator_salutation.enabled/value`
- `paused_title_prefix.enabled/value`
- `reminders.enabled`、时区、日间窗口、周期与额外提醒时间

配置器只更新 `AGENTS.md` 中带标记的受管片段，不覆盖其他规则。逐句音频使用文本、类型、声音和语速的内容哈希复用 `.m4a` 文件；书面和口语分别生成。若外置存储、macOS `say` 或所选声音不可用，只返回文字，不写入其他目录。Codex 内置 Voice 仍用于实时语音对话，逐句播放器属于 Skill 的独立离线附件功能。

### 使用

在 Codex 中打开项目并输入：

```text
初始化 Chief of Staff
```

也可以显式指定项目名：

```text
使用 $chief-of-staff 初始化这个项目，项目名为个人web。
```

未显式指定项目名时，初始化器默认使用项目根目录名称。项目名会写入 `.chief-of-staff/project.json`，同时生成：

```json
{
  "project_name": "个人web",
  "primary_task_title": "Chief of 个人web",
  "pin_primary_task": true,
  "report_approval_required": true,
  "require_goal_confirmation": true,
  "durable_goal_enabled": true,
  "execution_mode": "effective_throughput",
  "max_parallel_phase_lanes": 2,
  "no_evidence_checkpoint_limit": 2,
  "max_management_depth": 3,
  "auto_advance_low_impact": true,
  "proactive_follow_up": true,
  "visual_selection_gate": "disabled",
  "durable_child_scope": "same_project",
  "archive_completed_child_tasks": true,
  "projectless_child_policy": "temporary_subagents",
  "peer_coordination_enabled": true,
  "peer_contact_policy": "registered_same_project",
  "subagent_meetings_enabled": true,
  "max_meeting_participants": 3
}
```

Skill 会读取 `primary_task_title` 并把当前主任务重命名为该值；当 `pin_primary_task` 为 `true` 时，它随后会识别并置顶当前任务。只有工具确认成功后才会报告已置顶。

初始化器还会创建：

```text
AGENTS.md
.codex/
├── config.toml
└── agents/
    ├── scout.toml
    ├── implementer.toml
    ├── verifier.toml
    └── arbiter.toml
.chief-of-staff/
├── project.json
├── project-plan.json
├── task-registry.json
├── approval-queue.json
├── decisions.md
├── status.md
├── control-plane.json
└── throughput.json
```

初始化器支持重复运行。它会保留可变的项目状态；如果已有的受管说明或配置与模板冲突，则会在写入任何文件前停止。

检查已初始化项目：

```bash
python3 ~/.codex/skills/chief-of-staff/scripts/init_project.py \
  --target /项目路径 \
  --check
```

### 协作模型

```text
用户
└── Chief of 个人web
    ├── 产品负责人｜定义需求
    │   └── 临时用户研究 subagents
    ├── 技术负责人｜完成架构决策
    │   ├── 安全专家 subagent
    │   └── 接口专家 subagent
    └── 实施负责人｜交付功能
        └── 测试与复核 subagents
```

长期 Codex 任务拥有可见、独立且可以持续的上下文；临时 subagents 只完成边界明确的工作并向父任务汇报。主任务负责基于证据解决冲突并最终向用户汇报。

### 项目空间与 Recents

Chief 创建长期岗位前会读取自己的 Codex `projectId`，用同一个项目目标创建子岗位，并把该 ID 写入任务登记。这样岗位的上下文、工作区和状态都归属于正确项目。若 Chief 尚未处在已保存项目中，它会优先使用临时 subagents；只有确实需要独立长期历史时才请你先选择或保存项目。

Codex 会把长期任务视为可以独立恢复的任务，因此活动中的项目岗位仍可能出现在 Recents。这个入口的好处是集中显示运行、失败和等待人工处理的状态，避免必须逐个进入项目才能发现异常。当前版本采用折中生命周期：运行中、失败或待批复的岗位保持可见；最终汇报经你批准、证据写入项目状态且无需返工后，Chief 才将岗位归档。归档可恢复，不会删除任务 ID、结果摘要或项目内登记。

### 岗位对接与多 Agent 会议

Chief 会在 `task-registry.json` 中为确有工作交集的同项目岗位建立双向 `coordination_with` 关系。登记后的岗位可以直接发送结构化对接消息，讨论依赖、接口、证据或交接；对接结论或未解决冲突必须回传 Chief。普通对接不需要你审批，也不会绕过 Chief 形成第二套项目计划。

每个长期岗位可以自行召开临时 subagent 会议，默认最多三名参与者。会议必须有一个明确问题、互不重叠的角色、输入证据、停止条件和综合负责人。参与者默认只读，不能继续创建长期岗位；如需实施，仍只有一个写入者。岗位负责人等待全部结果后按证据综合，再将简明结论发给相关岗位与 Chief。

### 待回复 TODO 与提醒（可选）

提醒是个人级、跨项目服务，不会让每个 Chief 重复创建一套自动化。只有统一偏好中的 `reminders.enabled` 为 `true` 时，Skill 才创建或复用一个置顶的 `TODO｜待回复 Chief 汇总` 对话；它只收集 Chief 明确等待你审批、确认、决策、补充信息或权限选择、且尚无后续用户回复的事项。仅仅打开或阅读对话不会被误判为已回复。

示例预设采用北京时间 09:00–18:00 每小时一次（包含 09:00 和 18:00），并在 22:00 再提醒一次；时区、日间窗口、间隔和额外时间都可调整。保存偏好不会自行创建自动化，仍需 Skill 通过 Codex 的定时任务接口建立或更新。关闭时会暂停该策略登记的全部自动化，因此不会运行扫描，也不会发送通知；保留 TODO 对话和 ID 便于以后恢复。

### 汇报批复机制

启用默认的 `report_approval_required` 后，子岗位的普通过程消息不会打断你，但里程碑汇报和最终交接必须带唯一汇报编号，并在 Codex 中请求人工处理。Chief 在任一子任务有结果时会立即检查全部活跃子任务，把所有新汇报去重写入 `approval-queue.json`，再在主任务中一次性列出待批复事项。

你仍然只需要在 Chief 主任务中选择批准或退回修改。Chief 会把决定转发给对应子岗位；在收到你的明确决定之前，该岗位在登记中保持 `needs_attention`，也不会把沉默或无关消息视为默认批准。若运行环境不支持原生等待输入状态，子岗位使用 `REVIEW_REQUIRED` 标记，由 Chief 主任务发起人工审批作为降级方案。

汇报批准只表示你已审阅并接受该次交接，不会自动授权删除、发布、生产变更、支付、外发消息或扩大权限；这些高影响操作仍需单独确认。

### 目标闭环与主动推进

初始化后，Chief 会先根据项目上下文提出最终目标、交付物、验收标准、非目标和约束，请你确认或修改。新项目在你明确确认前只允许为澄清目标进行有限的只读侦察。旧项目迁移时允许已经开始的非高影响任务完成，但不会派发新任务或进入新阶段。确认结果和逐项验收证据保存在 `project-plan.json`。

目标确认后，Chief 将工作拆为阶段，并确保未完成项目始终满足以下之一：有岗位正在排队、工作或等待处理；正在等待你的具体决定；或者存在有证据且有解除条件的阻塞。如果本阶段岗位全部结束但最终验收仍未满足，Chief 会自动创建并推进下一阶段，而不是只回答“当前无待审批事项”。

默认层级为 `Chief → 阶段负责人 → 执行岗位/临时 subagents`。阶段负责人可以在授权范围内创建执行岗位；临时 subagents 不能继续创建长期岗位。需要第四层时，Chief 必须先说明原因、期限、岗位结构和不扩层的影响并向你申请。

未完成项目的 Chief 汇报固定包含最终目标、当前阶段、已验证进展、正在工作的岗位、距最终交付的差距和下一检查点。只有全部最终验收标准都有证据时才能宣布项目完成。

### 有效吞吐、创意与部署

`effective_throughput` 以已完成且有证据的验收为中心。默认至多两个无共享写入面的独立阶段并行；每个检查点必须关联具体验收证据，连续两个检查点无证据时，Chief 停止该线路并自查目标、范围、依赖、写入权、验收方法和阻塞原因。

只有最终目标已确认、验收可验证且没有待处理人工门时才可使用 `/goal`。创意总监在北京时间每天 11:00 和 20:00 执行有证据的扫描，最多保留一条待定建议；只读其他项目，不发消息、不改文件。偏好证据分为明确偏好、一致模式和单次假设；新项目建议至少需要两个不同项目的明确偏好或一致模式证据，并包含目标用户、最小验证、成功阈值和停止条件。

当云部署工作被明确纳入范围时，应在独立 registry 中登记目标与证据；该记录是库存与审计记录而非执行凭证。生产部署、生产变更、发布或回滚均须在操作前单独取得明确用户批准。

### 全局上下文无损接续

仓库同时提供 `context-handoff` Skill。它只使用最新输入 token 与模型上下文窗口的比值：75%刷新检查点，85%在安全边界创建 `原对话名｜续N`，95%进入紧急迁移。累计 token 和账户限额不会被误当成上下文占用。

项目迁移包保存在 `.codex/context-migrations/`，无项目任务保存在 `~/.codex/context-migrations/`。新对话必须返回 `MIGRATION_READY` 并核对目标、审批、任务关系、写入权、Git 状态、证据、下一步和全局规则，之后旧对话才归档；旧对话不会删除。若原生压缩降低占用则取消过期触发；若无法证明同一脏工作树连续性则保留旧对话并请求人工选择。

### 当前限制

- 第一版不修改 Codex 客户端界面；只在宿主已提供阻塞式选择面板时调用它，否则使用对话或 CLI 配置。
- 关闭 Codex 可能会停止正在运行的任务；持久状态保存在项目文件和 Codex 任务历史中。
- 当前不安装 AWS CLI Agent Orchestrator 等外置控制台；`control-plane.json` 仅预留未来适配入口。

<a id="english"></a>

## English

[Go to 中文](#中文)

### What it does

Chief of Staff gives each Codex project a single user-facing control point. The main task is named dynamically as `Chief of <project name>`, for example `Chief of Personal Web`, and is pinned automatically after initialization. You talk to that main task; it decomposes the objective, creates durable tasks when separate long-lived context is useful, collects structured handoffs, and consolidates the final report.

Each durable task can use installed Skills automatically and can summon temporary subagents for bounded research, review, testing, or discussion.

### Key features

- A distinguishable main task name for every project: `Chief of <project name>`.
- Automatic pinning of the main task after initialization.
- Human review gates for milestone and final reports, with batch collection so simultaneous updates are not missed.
- Mandatory user confirmation of the final goal, deliverables, and acceptance criteria before implementation.
- Continuous phase dispatch until final acceptance, with a three-level management hierarchy by default.
- One accountable main task for user communication.
- Durable tasks named `Role｜Work outcome`.
- Temporary subagent meetings inside durable tasks.
- Luna for read-only exploration, Terra as the sole implementation writer, and Sol for high-risk arbitration by default.
- One writer per file, external record, branch, deployment target, or deliverable.
- Structured handoffs that separate verified facts, inference, open questions, risks, and next steps.
- Explicit user approval before deletion, production changes, releases, payments, external messages, or permission expansion.
- An optional pause-title policy adds `已暂停｜` only after an explicit pause and removes it after an explicit resume; idle, blocked, and awaiting-user states do not trigger it.
- Optional American-English coaching can cover both work and casual chat, with separate written, spoken, idiom, and audio outputs.
- Persistent project state with a reserved adapter seam for a future external control plane.
- Effective throughput: at most two independent phase lanes, checkpoint evidence, and a stop/self-check after two evidence-free checkpoints.
- `/goal` only after a confirmed, testable goal with no human gate; durable goals never bypass protected-action approvals.
- Evidence-backed Creative Director scans at 11:00 and 20:00 Beijing time, with no more than one pending recommendation and preference evidence classified as `explicit`, `confirmed_pattern`, or `hypothesis`.
- An independent cloud deployment registry; a registry record never authorizes production work.
- An optional human visual-selection gate: projects submit clickable previews to a configured review hub, and no unselected option may become the final version.
- An optional pinned, cross-project unanswered-Chief TODO with configurable reminders; disabling it stops all reminder runs.

### Requirements

- A current Codex desktop app, Codex CLI, or IDE extension with Skills and subagents enabled.
- Python 3.9 or newer for the project initializer.

### Install

Clone this repository, then copy or symlink it into your personal Codex Skills directory:

```bash
git clone https://github.com/rong2qi/chief-of-staff-codex.git chief-of-staff
cp -R chief-of-staff ~/.codex/skills/chief-of-staff
cp -R chief-of-staff/context-handoff ~/.codex/skills/context-handoff
```

Open a new Codex task after installation. Codex normally detects Skill changes automatically; restart it if the Skill does not appear.

### First-use preference setup

Cloning and copying the Skill never runs setup by itself. Setup begins only when you enter one of these prompts:

```text
$chief-of-staff configure my preferences
$chief-of-staff initialize this project
```

If no profile exists, a Codex host with a native blocking selection panel presents three questions in one form:

1. Preset: `Core Chief`, `Operator-controlled + bilingual coaching`, or `Custom`.
2. Salutation: neutral, `妈妈`, or a custom value.
3. Data location: the default personal directory, an external/custom absolute path, or the current project only.

Codex previews the enabled rules, destination, and fallback behavior, then writes only after a final Apply confirmation. Custom mode opens a second form for visual approval, casual-chat coaching, written/spoken/idiom notes, both audio clips, voice and rate, pause-title behavior, TODO reminders, and reminder cadence. A CLI or IDE without the native panel asks the same questions conversationally; it does not simulate a pop-up.

For deterministic non-interactive setup:

```bash
python3 ~/.codex/skills/chief-of-staff/scripts/configure_preferences.py \
  --preset operator-controlled-bilingual \
  --scope global \
  --salutation Operator \
  --voice Samantha \
  --data-root /Volumes/ExternalDrive/chief-data
```

A custom data root must already exist. A missing or unwritable external disk fails safely with no local fallback. Global preferences are configured once and inherited by future projects; use `$chief-of-staff reconfigure my preferences` to run onboarding again. The public `core` preset leaves every personal rule disabled.

The unified profile controls visual selection, American-English coaching and casual-chat coverage, written/spoken audio, voice, rate, salutation, pause-title prefix, and reminder schedule. The configurator replaces only a marked managed block in `AGENTS.md`. Audio clips are separate content-addressed `.m4a` files, so repeated text reuses the same file. Missing storage, tools, or voice support returns text only and never writes elsewhere. Built-in Codex Voice remains the realtime conversation mode; these clips are separate offline attachments.

### Use

Open the project in Codex and say:

```text
Initialize Chief of Staff for this project.
```

You can also provide the project name explicitly:

```text
Use $chief-of-staff to initialize this project with the project name Personal Web.
```

When no project name is supplied, the initializer uses the project root directory name. It writes the name and generated task title to `.chief-of-staff/project.json`:

```json
{
  "project_name": "Personal Web",
  "primary_task_title": "Chief of Personal Web",
  "pin_primary_task": true,
  "report_approval_required": true,
  "require_goal_confirmation": true,
  "max_management_depth": 3,
  "auto_advance_low_impact": true,
  "proactive_follow_up": true,
  "visual_selection_gate": "disabled",
  "durable_child_scope": "same_project",
  "archive_completed_child_tasks": true,
  "projectless_child_policy": "temporary_subagents",
  "peer_coordination_enabled": true,
  "peer_contact_policy": "registered_same_project",
  "subagent_meetings_enabled": true,
  "max_meeting_participants": 3
}
```

The Skill reads `primary_task_title` and renames the current main task to that exact value. When `pin_primary_task` is `true`, it then resolves and pins the current task, reporting success only after tool confirmation.

The initializer also creates:

```text
AGENTS.md
.codex/
├── config.toml
└── agents/
    ├── scout.toml
    ├── implementer.toml
    ├── verifier.toml
    └── arbiter.toml
.chief-of-staff/
├── project.json
├── project-plan.json
├── task-registry.json
├── approval-queue.json
├── decisions.md
├── status.md
├── control-plane.json
└── throughput.json
```

The initializer is idempotent. It preserves mutable project state and stops without writing when a managed instruction or configuration file conflicts with the template.

Validate an initialized project with:

```bash
python3 ~/.codex/skills/chief-of-staff/scripts/init_project.py \
  --target /path/to/project \
  --check
```

### Coordination model

```text
User
└── Chief of Personal Web
    ├── Product Lead｜Define requirements
    │   └── Temporary research subagents
    ├── Technical Lead｜Decide architecture
    │   ├── Security subagent
    │   └── API subagent
    └── Implementation Lead｜Deliver the change
        └── Verification subagents
```

Durable Codex tasks retain visible, independent context. Temporary subagents handle bounded work and report to their parent task. The main task remains responsible for reconciling evidence and reporting to the user.

### Project space and Recents

Before creating a durable role, the Chief resolves its Codex `projectId`, creates the child against the same project target, and records that ID in the task registry. If the Chief is not in a saved project, it defaults to temporary subagents and asks the user to select or save a project only when separate durable history is necessary.

Codex treats durable tasks as independently resumable tasks, so active project roles may still appear in Recents. That shared view is useful for surfacing running, failed, and needs-attention states without opening every project. This Skill therefore uses a lifecycle policy: active or actionable roles remain visible; after the user approves a final handoff, evidence is recorded, and no retry remains, the Chief archives the child. Archiving is reversible and preserves the task ID, result summary, and project registry record.

### Peer coordination and multi-agent meetings

The Chief creates symmetric `coordination_with` edges in `task-registry.json` for same-project roles with a real dependency. Registered peers may directly exchange structured messages about interfaces, evidence, dependencies, or handoffs, then copy the outcome or unresolved conflict back to the Chief. Routine coordination needs no human approval and cannot create a competing project plan.

Every durable role may convene a temporary subagent meeting with up to three participants by default. A meeting has one question, non-overlapping roles, evidence inputs, a stopping condition, and a synthesis owner. Participants are read-only by default and cannot create durable roles; if implementation is included, exactly one participant owns the write surface. The parent waits for all results, reconciles them by evidence, and sends one concise outcome to affected peers and the Chief.

### Unanswered-Chief TODO and reminders (optional)

Reminders are one personal, cross-project service rather than one automation per Chief. Only when `reminders.enabled` is `true` does the Skill create or reuse a pinned `TODO｜待回复 Chief 汇总` thread. It includes only Chiefs that explicitly await approval, confirmation, a decision, more information, or a permission choice and have no later resolving user reply. Merely opening or reading a thread does not clear an item.

The example preset uses every Beijing-time hour from 09:00 through 18:00 inclusive, plus 22:00; timezone, daytime window, interval, and additional times are configurable. Saving a preference does not create an automation by itself: the Skill still uses Codex's scheduled-task interface to create or update it. Disabling pauses every automation recorded by the policy, producing no scan runs or notifications while preserving the TODO thread and identifiers for later re-enablement.

### Report approval workflow

With the default `report_approval_required` setting enabled, routine progress commentary does not interrupt you, but milestone reports and final handoffs carry a unique report ID and request human review in Codex. When any child produces a result, the Chief immediately snapshots every active child, deduplicates all new reports into `approval-queue.json`, and presents one approval batch in the main task.

You still approve or request changes only in the Chief task. The Chief relays each decision to the matching child; until an explicit decision is received, its registry status remains `needs_attention`, and silence or an unrelated message never counts as approval. If the runtime cannot open a native blocking review request, the child emits a `REVIEW_REQUIRED` marker and the Chief opens the human-review request as a fallback.

Report approval acknowledges that handoff only. It does not authorize deletion, release, production changes, payments, external messages, or permission expansion; those high-impact actions still require separate confirmation.

### Goal closure and proactive progression

After initialization, the Chief drafts the final goal, deliverables, acceptance criteria, non-goals, and constraints from available project context and asks you to confirm or revise them. A new project permits only bounded read-only discovery before explicit confirmation. During migration, already-running non-high-impact tasks may finish, but no new task or phase starts. The confirmed contract and criterion-level evidence live in `project-plan.json`.

Once confirmed, the Chief divides the work into phases. Until final acceptance, the project must have an active, queued, or attention-needed role; be waiting for an exact user decision; or be blocked with evidence and a release condition. If every role in a phase stops while final acceptance remains unmet, the Chief dispatches the next safe in-scope phase instead of replying only that no approval is pending.

The default hierarchy is `Chief → Phase Lead → Execution Role/temporary subagents`. Authorized phase leads may create execution roles; temporary subagents cannot create durable roles. A fourth management level requires the Chief to request approval with the reason, duration, proposed structure, and impact of refusal.

Every unfinished-project report includes the final goal, current phase, verified progress, active roles, remaining delivery gap, and next checkpoint. The Chief may declare completion only when every final acceptance criterion has supporting evidence.

### Global loss-aware context rollover

The repository also includes `context-handoff`. It uses only newest input tokens divided by the model context window: checkpoint at 75%, create `Original title｜Continuation N` at a safe boundary at 85%, and prioritize migration at 95%. Cumulative and account usage are ignored.

Project bundles live in `.codex/context-migrations/`; projectless bundles live in `~/.codex/context-migrations/`. A successor must return `MIGRATION_READY` and match goals, approvals, task graph, write ownership, Git state, evidence, next action, and global instructions before the retained predecessor is archived. Native compaction cancels stale triggers; unproven dirty-worktree continuity requires a user decision.

### Current limits

- Version 1 does not modify the Codex client UI. It uses a native blocking selection panel only when the host already provides one, with conversational and CLI fallbacks.
- Closing Codex may stop active work; persistent coordination state is stored in project files and Codex task history.
- An external control plane such as AWS CLI Agent Orchestrator is not installed. `control-plane.json` reserves a future integration point.

## Repository contents / 仓库内容

- `SKILL.md`: Skill routing and operating instructions / Skill 路由与操作说明。
- `scripts/init_project.py`: safe project initializer and validator / 安全的项目初始化与校验脚本。
- `scripts/configure_preferences.py`: idempotent preference onboarding / 幂等偏好配置器。
- `scripts/render_english_audio.py`: content-addressed written/spoken audio / 书面与口语逐句音频。
- `assets/project-template/`: generated project contract and agent profiles / 项目契约与角色配置模板。
- `assets/operator-preferences.example.json`: privacy-safe core defaults / 隐私安全的核心默认偏好。
- `assets/presets/`: opt-in preference presets / 可主动启用的偏好预设。
- `references/`: coordination protocol and persistent state schema / 协调协议与持久状态结构。
- `references/operator-preferences.md`: onboarding, schema, and privacy behavior / 首次配置、结构与隐私行为。
- `assets/reminder-policy.example.json`: optional personal reminder policy example / 可选的个人提醒策略示例。
- `agents/openai.yaml`: Codex UI metadata and implicit invocation policy / Codex 界面元数据与自动调用策略。
- `context-handoff/`: global context checkpoint and verified rollover Skill / 全局上下文检查点与校验接续 Skill。

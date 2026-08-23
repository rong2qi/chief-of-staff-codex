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
- 长期任务内部可以召开临时子代理会议。
- 默认使用 Luna 进行只读侦察、Terra 作为唯一实施者、Sol 处理高风险裁决。
- 同一文件、外部记录、分支、部署目标或交付物同时只有一个写入者。
- 汇报明确区分已验证事实、推断、待确认项、风险和下一步。
- 删除、生产变更、发布、支付、外发消息和扩大权限前必须取得用户明确授权。
- 使用项目文件保存协调状态，并为未来外置控制平面预留适配接口。

### 环境要求

- 支持 Skills 和 subagents 的新版 Codex 桌面端、Codex CLI 或 IDE 扩展。
- 项目初始化器需要 Python 3.9 或更高版本。

### 安装

克隆本仓库，然后复制或链接到个人 Codex Skills 目录：

```bash
git clone https://github.com/rong2qi/chief-of-staff-codex.git chief-of-staff
cp -R chief-of-staff ~/.codex/skills/chief-of-staff
```

安装后新建一个 Codex 任务。Codex 通常会自动检测 Skill 变化；如果没有出现，请重启 Codex。

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
  "max_management_depth": 3,
  "auto_advance_low_impact": true,
  "proactive_follow_up": true
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
└── control-plane.json
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

### 汇报批复机制

启用默认的 `report_approval_required` 后，子岗位的普通过程消息不会打断你，但里程碑汇报和最终交接必须带唯一汇报编号，并在 Codex 中请求人工处理。Chief 在任一子任务有结果时会立即检查全部活跃子任务，把所有新汇报去重写入 `approval-queue.json`，再在主任务中一次性列出待批复事项。

你仍然只需要在 Chief 主任务中选择批准或退回修改。Chief 会把决定转发给对应子岗位；在收到你的明确决定之前，该岗位在登记中保持 `needs_attention`，也不会把沉默或无关消息视为默认批准。若运行环境不支持原生等待输入状态，子岗位使用 `REVIEW_REQUIRED` 标记，由 Chief 主任务发起人工审批作为降级方案。

汇报批准只表示你已审阅并接受该次交接，不会自动授权删除、发布、生产变更、支付、外发消息或扩大权限；这些高影响操作仍需单独确认。

### 目标闭环与主动推进

初始化后，Chief 会先根据项目上下文提出最终目标、交付物、验收标准、非目标和约束，请你确认或修改。新项目在你明确确认前只允许为澄清目标进行有限的只读侦察。旧项目迁移时允许已经开始的非高影响任务完成，但不会派发新任务或进入新阶段。确认结果和逐项验收证据保存在 `project-plan.json`。

目标确认后，Chief 将工作拆为阶段，并确保未完成项目始终满足以下之一：有岗位正在排队、工作或等待处理；正在等待你的具体决定；或者存在有证据且有解除条件的阻塞。如果本阶段岗位全部结束但最终验收仍未满足，Chief 会自动创建并推进下一阶段，而不是只回答“当前无待审批事项”。

默认层级为 `Chief → 阶段负责人 → 执行岗位/临时 subagents`。阶段负责人可以在授权范围内创建执行岗位；临时 subagents 不能继续创建长期岗位。需要第四层时，Chief 必须先说明原因、期限、岗位结构和不扩层的影响并向你申请。

未完成项目的 Chief 汇报固定包含最终目标、当前阶段、已验证进展、正在工作的岗位、距最终交付的差距和下一检查点。只有全部最终验收标准都有证据时才能宣布项目完成。

### 当前限制

- 第一版只使用 Codex 原生能力，不修改 Codex 客户端界面。
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
- Persistent project state with a reserved adapter seam for a future external control plane.

### Requirements

- A current Codex desktop app, Codex CLI, or IDE extension with Skills and subagents enabled.
- Python 3.9 or newer for the project initializer.

### Install

Clone this repository, then copy or symlink it into your personal Codex Skills directory:

```bash
git clone https://github.com/rong2qi/chief-of-staff-codex.git chief-of-staff
cp -R chief-of-staff ~/.codex/skills/chief-of-staff
```

Open a new Codex task after installation. Codex normally detects Skill changes automatically; restart it if the Skill does not appear.

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
  "proactive_follow_up": true
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
└── control-plane.json
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

### Report approval workflow

With the default `report_approval_required` setting enabled, routine progress commentary does not interrupt you, but milestone reports and final handoffs carry a unique report ID and request human review in Codex. When any child produces a result, the Chief immediately snapshots every active child, deduplicates all new reports into `approval-queue.json`, and presents one approval batch in the main task.

You still approve or request changes only in the Chief task. The Chief relays each decision to the matching child; until an explicit decision is received, its registry status remains `needs_attention`, and silence or an unrelated message never counts as approval. If the runtime cannot open a native blocking review request, the child emits a `REVIEW_REQUIRED` marker and the Chief opens the human-review request as a fallback.

Report approval acknowledges that handoff only. It does not authorize deletion, release, production changes, payments, external messages, or permission expansion; those high-impact actions still require separate confirmation.

### Goal closure and proactive progression

After initialization, the Chief drafts the final goal, deliverables, acceptance criteria, non-goals, and constraints from available project context and asks you to confirm or revise them. A new project permits only bounded read-only discovery before explicit confirmation. During migration, already-running non-high-impact tasks may finish, but no new task or phase starts. The confirmed contract and criterion-level evidence live in `project-plan.json`.

Once confirmed, the Chief divides the work into phases. Until final acceptance, the project must have an active, queued, or attention-needed role; be waiting for an exact user decision; or be blocked with evidence and a release condition. If every role in a phase stops while final acceptance remains unmet, the Chief dispatches the next safe in-scope phase instead of replying only that no approval is pending.

The default hierarchy is `Chief → Phase Lead → Execution Role/temporary subagents`. Authorized phase leads may create execution roles; temporary subagents cannot create durable roles. A fourth management level requires the Chief to request approval with the reason, duration, proposed structure, and impact of refusal.

Every unfinished-project report includes the final goal, current phase, verified progress, active roles, remaining delivery gap, and next checkpoint. The Chief may declare completion only when every final acceptance criterion has supporting evidence.

### Current limits

- Version 1 uses native Codex capabilities and does not modify the Codex client UI.
- Closing Codex may stop active work; persistent coordination state is stored in project files and Codex task history.
- An external control plane such as AWS CLI Agent Orchestrator is not installed. `control-plane.json` reserves a future integration point.

## Repository contents / 仓库内容

- `SKILL.md`: Skill routing and operating instructions / Skill 路由与操作说明。
- `scripts/init_project.py`: safe project initializer and validator / 安全的项目初始化与校验脚本。
- `assets/project-template/`: generated project contract and agent profiles / 项目契约与角色配置模板。
- `references/`: coordination protocol and persistent state schema / 协调协议与持久状态结构。
- `agents/openai.yaml`: Codex UI metadata and implicit invocation policy / Codex 界面元数据与自动调用策略。

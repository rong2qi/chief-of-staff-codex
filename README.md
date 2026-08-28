# Chief of Staff for Codex / Codex 幕僚长

> 通过一个统一负责的主任务、按职务命名的长期任务，以及临时子代理会议来协调 Codex 项目。
>
> Coordinate a Codex project through one accountable main task, durable role-based tasks, and temporary subagent meetings.

[中文](#中文) · [English](#english)

<a id="中文"></a>

## 中文

[跳转到 English](#english)

### 它能做什么

Chief of Staff 为每个 Codex 项目提供一个统一的用户交互入口。主任务会根据项目名自动命名为 `Chief of <项目名>`，例如 `Chief of 个人web`。普通 Chief 初始化后默认不置顶；中央角色和妈妈批准的可选席位才进入置顶流程。你只需要和这个主任务交流；它负责拆解目标、创建需要长期独立上下文的任务、收集结构化汇报，并向你提供最终总结。

每个长期任务可以根据工作内容自动选择已安装的 Skill，也可以召集临时 subagents 完成范围明确的调研、评审、测试或讨论。

### 核心能力

- 每个项目拥有可区分的主任务名称：`Chief of <项目名>`。
- 普通 Chief 默认不置顶；general office、TODO、创意总监、上下文迁移监控和测试总监五个中央角色，以及妈妈批准的可选产品 Chief 席位，才需要置顶和受控继承。测试总监负责跨项目质量政策与证据审查，不是第二个面向妈妈的审批入口，也不自动取得项目写权限。操作回执不算证据，eligible lineage 只有在精确 task ID 出现在新的 `pinnedThreads` 查询中后才能切换权威入口。
- 默认采用 `exception_only`：Chief 验收普通岗位里程碑和最终交接，只有列明例外与项目最终完成才进入操作者批复；Chief 会批量收集同时到达的汇报，避免遗漏。
- Chief 必须先与你确认最终目标、交付物和验收标准；未达成最终验收前持续分阶段推进。
- 目标确认后必须分类：交付型项目先由 depth-2 产品经理完成四路产品发现与立项门，才可创建或启动生产岗位；纯同步/推送、会议总结、备案/流程推进或只读汇总可记录理由后豁免，范围扩展时立即重分类。
- 项目启动先做覆盖优先的能力检索：扫描内置/已安装能力、可用插件与 Skill、官方文档、维护活跃的开源项目和可复用外部配置；技术栈确定后再做一次栈级复核。不得为了省 Token 或时间直接闭门重造，测试相关候选由测试总监审查；付费、扩权、生产与其他高风险动作仍需单独批准。
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
- 创意总监在北京时间每天 11:00 和 20:00 执行有证据的主动扫描，而非空转目标；最多一条待定创意建议。启用视觉门时，它还是唯一面向操作者的视觉审阅中心：接收项目预览包、维护视觉待决队列，并只把操作者原话回传来源 Chief；除此以外只读、不主动干预、不修改项目文件。
- 云部署目标和证据登记在独立 deployment registry 中；登记不是授权，生产部署、生产变更、发布或回滚仍须在操作前取得明确用户批准。
- 可选的视觉人工门要求项目先提供可点击预览，并只提交给置顶的 `Chief of Creative Direction｜创意总监`；项目 Chief、岗位、“一人之下”和 TODO 不得复制同一视觉请求。操作者明确选择前，未选方案不得成为最终版本。
- 可选的暂停标题策略会在操作者明确暂停时添加 `已暂停｜`，明确恢复时移除。空闲、阻塞或等待批复不会被误判为暂停。
- 可选的美式英语教学可覆盖工作消息和闲聊，并提供书面、口语与地道用法文本。`host_builtin` 只交给客户端内置语音/朗读，不生成独立音频；仅主动选择 `auto` 或 `macos_say` 离线附件模式时才分别生成书面与口语 `.m4a`。
- 可选启用一个跨项目、置顶的 Chief 待回复 TODO，并按个人策略定时提醒；关闭后完全不运行提醒。

### Token 成本与适用对象

Chief of Staff 是一个强调长期上下文、岗位分工、独立复核和持续跟进的编排层，因此可能让 Token 用量明显高于完成同一项工作的单代理对话。每个长期任务和 subagent 都会执行自己的模型推理与工具调用；并发岗位越多、上下文越长、复核轮次越多，增量通常越明显。OpenAI 官方文档同样说明，subagent 工作流会比可比的单代理运行消耗更多 Token。[OpenAI Subagents 文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)

- **企业或成熟团队：推荐直接使用。** 它更适合跨产品、研发、测试、合规和部署的长周期项目，尤其是需要职责隔离、审批记录、证据链和统一汇报的场景。建议同时设置并发上限、模型路由、阶段预算和停止条件。
- **个人用户或新手：建议按需启用。** 简单任务不要启动完整 Chief 层级；优先使用 `core` 预设、单阶段/单写入者和更低成本模型。编码、诊断、审查和证据化执行可显式调用本仓库原创的 `$kai-lean-execution`，在不缩小目标或跳过验收的前提下减少无效调查、重复计划和冗长日志；长对话迁移仍使用 `context-handoff`。该 Skill 不承诺固定比例的 Token 节省。
- **不要以“烧 Token”作为成果指标。** 应以完成交付物、验证证据、阻塞解除时间和最终验收为准。降 Token Skill 也不能代替人工审批、完整验收或原始记录留存。

### 环境要求

- 支持 Skills 和 subagents 的新版 Codex 桌面端、Codex CLI 或 IDE 扩展。
- 项目初始化器需要 Python 3.9 或更高版本。

### 安装

克隆本仓库，然后复制或链接到个人 Codex Skills 目录：

```bash
git clone https://github.com/rong2qi/chief-of-staff-codex.git chief-of-staff
cp -R chief-of-staff ~/.codex/skills/chief-of-staff
cp -R chief-of-staff/context-handoff ~/.codex/skills/context-handoff
cp -R chief-of-staff/kai-lean-execution ~/.codex/skills/kai-lean-execution
```

安装后新建一个 Codex 任务。Codex 通常会自动检测 Skill 变化；如果没有出现，请重启 Codex。

### 首次偏好配置

`git clone` 和复制 Skill 本身不会运行任何脚本，也不会立刻弹窗。首次输入以下任一命令时才会开始配置：

```text
$chief-of-staff 配置个人偏好
$chief-of-staff 初始化这个项目
```

如果还没有偏好档案，支持原生阻塞式选择面板的 Codex 客户端会先显示一张三问表单：

1. 预设：`核心 Chief`、`操作者主导 + 双语教学` 或 `自定义`；表单会同时显示“企业/成熟团队推荐完整 Chief（配置并发、模型、阶段预算和停止条件）”以及“个人/小白推荐核心 Chief、单阶段/单写入者和低成本模型”的说明；
2. 称呼：中性、`妈妈` 或自定义；
3. 数据位置：默认个人目录、外置磁盘/自定义绝对路径，或仅当前项目。

个人/小白还会看到本仓库原创、显式调用的 `$kai-lean-execution` 建议；向导不会自动调用它或为当前任务注入额外代理。Codex 随后展示将启用的规则、写入位置、语音方式和降级行为，并只在用户选择“应用”后写入。选择“自定义”时，第二张表单可以分别控制视觉确认、闲聊英语教学、书面/口语/地道用法、Codex 内置语音或离线音频附件、声音与语速、暂停标题、TODO 提醒及其周期。没有原生面板的 CLI 或 IDE 会使用同样问题进行简短对话，不会伪造弹窗。

也可完全跳过交互：

```bash
python3 ~/.codex/skills/chief-of-staff/scripts/configure_preferences.py \
  --preset operator-controlled-bilingual \
  --scope global \
  --salutation 妈妈 \
  --audio-provider host_builtin \
  --data-root /Volumes/ExternalDrive/chief-data
```

自定义数据目录必须已经存在；磁盘缺失或权限不足时配置会失败，不会回退写入本机。全局偏好只配置一次，未来项目自动继承；输入 `$chief-of-staff 重新配置个人偏好` 可再次打开向导。公共版默认 `core`，所有个人化规则关闭。

统一配置文件支持以下开关：

- `governance_model.enabled`（主席负责制）
- `governance_model.continuation_policy.enabled`（安全范围内默认持续推进）
- `project_start_capability_discovery.enabled`（项目启动能力深搜与栈级复核）
- `visual_selection_gate.enabled`
- `american_english_coaching.enabled` 与 `include_casual_chat`
- `audio_playback.enabled`、`provider`、`clips`、`voice`、`rate` 与 `storage_root`
- `operator_salutation.enabled/value`
- `paused_title_prefix.enabled/value`
- `reminders.enabled`、时区、日间窗口、周期与额外提醒时间

配置器只更新 `AGENTS.md` 中带标记的受管片段，不覆盖其他规则。双语预设默认采用 `host_builtin`：Skill 仅提供书面、口语和地道用法文本，由 Codex/ChatGPT 客户端的内置语音或朗读控件负责播放，不生成音频文件，也不声称能自动播放某一句。仅当用户主动选择 `auto` 或 `macos_say` 离线附件模式时，才分别为启用的书面和口语文本生成内容寻址的 `.m4a`；外置存储、macOS `say` 或所选声音不可用时只返回文字，不写入其他目录。

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
  "pin_primary_task": false,
  "report_review_mode": "exception_only",
  "report_approval_required": false,
  "governance_model": "standard",
  "operator_role": "operator",
  "continuation_policy": "standard",
  "ordinary_failure_policy": "bounded_repair_cycle",
  "continuation_escalation_policy": "existing_approval_boundaries",
  "project_classification_policy": "classify_after_goal_confirmation",
  "deliverable_product_discovery_policy": "required_before_production",
  "production_start_policy": "deny_until_product_discovery_passed_or_coordination_exempt",
  "product_discovery_state_file": ".chief-of-staff/product-discovery.json",
  "legacy_allowlist_digest": null,
  "require_goal_confirmation": true,
  "durable_goal_enabled": true,
  "execution_mode": "effective_throughput",
  "max_parallel_phase_lanes": 2,
  "no_evidence_checkpoint_limit": 2,
  "max_management_depth": 3,
  "auto_advance_low_impact": true,
  "proactive_follow_up": true,
  "visual_selection_gate": "disabled",
  "visual_review_hub_title": "Chief of Creative Direction｜创意总监",
  "durable_child_scope": "same_project",
  "archive_completed_child_tasks": true,
  "projectless_child_policy": "temporary_subagents",
  "peer_coordination_enabled": true,
  "peer_contact_policy": "registered_same_project",
  "subagent_meetings_enabled": true,
  "max_meeting_participants": 3
}
```

初始化时 `.chief-of-staff/product-discovery.json` 为 `pending/unclassified`，不会猜测项目类型。目标确认后的纯协调项目示例：

```json
{
  "classification_status": "classified",
  "project_classification": "coordination_only",
  "product_manager_required": false,
  "exemption_reason": "仅同步并推送已经批准的变更",
  "gate_status": "exempt"
}
```

交付型项目改用 `deliverable_project`，任命产品经理并完成四条证据线后，`gate_status` 才能变为 `passed`。

Skill 会读取 `primary_task_title` 并把当前主任务重命名为该值。普通 Chief 默认不置顶（`pin_primary_task=false`），未置顶不是故障。general office、TODO、Creative Director、context migration monitor 和 Testing Director 五个中央角色强制置顶；可选产品 Chief 必须先由一般办公室形成最多 3 名、最多 1 个待决包，再由 TODO 只读核验身份、时效、重复、证据新鲜度、容量与 lineage，最后由妈妈逐项批准任命和置顶。默认最多 6 个可选席位，并保护人工 non-Chief pins；历史保留席位统一称为 grandmothered optional Chiefs，在价值复核前保持现状但不自动继承。容量满时只给 paired replacement recommendation，不自动挤出。置顶批准不等于目标确认，也不授权工程、设计或生产，产品经理与四条 discovery lane 的产品门保持不变。仅 mandatory/approved lineage 可在安全核心交接候选后建立一个 replacement；自动化 parity 与 fresh `list_threads` 精确 ID 复核必须在最终 `MIGRATION_READY`、接管和归档 predecessor 前通过，`pinned:true` 回执不是证据。

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
├── pin-state.json
├── project-plan.json
├── product-discovery.json
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
    ├── 产品经理｜产品发现与立项（交付型项目必需）
    │   ├── 项目立项 subagent
    │   ├── 需求分析 subagent
    │   ├── 市场调研 subagent
    │   └── 架构可行性 subagent
    ├── 技术负责人｜完成架构决策
    │   ├── 安全专家 subagent
    │   └── 接口专家 subagent
    └── 实施负责人｜交付功能
        └── 测试与复核 subagents
```

长期 Codex 任务拥有可见、独立且可以持续的上下文；临时 subagents 只完成边界明确的工作并向父任务汇报。主任务负责基于证据解决冲突并最终向用户汇报。

### 项目空间与 Recents

Chief 创建长期岗位前会读取自己的 Codex `projectId`，用同一个项目目标创建子岗位，并把该 ID 写入任务登记。这样岗位的上下文、工作区和状态都归属于正确项目。若 Chief 尚未处在已保存项目中，它会优先使用临时 subagents；只有确实需要独立长期历史时才请你先选择或保存项目。

Codex 会把长期任务视为可以独立恢复的任务，因此活动中的项目岗位仍可能出现在 Recents。这个入口的好处是集中显示运行、失败和等待处理的状态，避免必须逐个进入项目才能发现异常。当前版本采用折中生命周期：运行中、失败或待处理的岗位保持可见；普通最终汇报经 Chief 按 `exception_only` 审查、证据写入项目状态且无需返工后才归档，项目最终完成仍由操作者确认。归档可恢复，不会删除任务 ID、结果摘要或项目内登记。

### 岗位对接与多 Agent 会议

Chief 会在 `task-registry.json` 中为确有工作交集的同项目岗位建立双向 `coordination_with` 关系。登记后的岗位可以直接发送结构化对接消息，讨论依赖、接口、证据或交接；对接结论或未解决冲突必须回传 Chief。普通对接不需要你审批，也不会绕过 Chief 形成第二套项目计划。

每个长期岗位可以自行召开临时 subagent 会议，默认最多三名参与者。会议必须有一个明确问题、互不重叠的角色、输入证据、停止条件和综合负责人。参与者默认只读，不能继续创建长期岗位；如需实施，仍只有一个写入者。岗位负责人等待全部结果后按证据综合，再将简明结论发给相关岗位与 Chief。

### 待回复 TODO 与提醒（可选）

提醒是个人级、跨项目服务，不会让每个 Chief 重复创建一套自动化。只有统一偏好中的 `reminders.enabled` 为 `true` 时，Skill 才创建或复用一个置顶的 `TODO｜待回复 Chief 汇总` 对话；它只收集 Chief 明确等待你审批、确认、决策、补充信息或权限选择、且尚无后续用户回复的事项。视觉选择只认 `Chief of Creative Direction｜创意总监` 为权威来源：项目 Chief、岗位、“一人之下”和旧审阅中心中的副本全部排除，并把创意总监持有的多个视觉 ID 合并为一个待回复入口。仅仅打开或阅读对话不会被误判为已回复。

### 视觉决策只进创意总监

启用 `visual_selection_gate` 后，项目 Chief 负责制作或组织可点击的 NON-FINAL 预览，但只能把稳定决策 ID、差异、证据和影响提交给唯一置顶的 `Chief of Creative Direction｜创意总监`。创意总监可以同时持有多个视觉待决项，并将新变化合并成一条简洁审阅消息；“最多一条待定建议”的限制只约束主动创意建议，不限制项目送来的视觉审批。

创意总监不能替操作者选择、实施设计、安装构建或修改来源项目。收到操作者明确决定后，它只把原话、决策 ID 和边界回传来源 Chief。若操作者没有及时回复，创意总监保持等待，不重复催促；后续由统一 TODO 扫描创意总监，而不是让每个项目再次提醒。

示例预设采用北京时间 09:00–18:00 每小时一次（包含 09:00 和 18:00），并在 22:00 再提醒一次；时区、日间窗口、间隔和额外时间都可调整。保存偏好不会自行创建自动化，仍需 Skill 通过 Codex 的定时任务接口建立或更新。关闭时会暂停该策略登记的全部自动化，因此不会运行扫描，也不会发送通知；保留 TODO 对话和 ID 便于以后恢复。

### 汇报批复机制

默认 `report_review_mode` 为 `exception_only`。子岗位仍须提交唯一汇报编号、证据、风险和下一步，但普通进度与岗位最终交接由项目 Chief 按执行契约审查，不再直接请求操作者批准。Chief 会检查范围、唯一写入面、验收证据、测试、冲突和高影响边界，并把审查依据写入 `approval-queue.json`。

只有目标确认、实质产品选择、视觉选择、高影响操作、安全问题、范围或写入权冲突、失败/证据不足、扩层和项目最终交付才升级给操作者。例外请求使用 `USER_ACTION_REQUIRED`；普通岗位交接使用 `CHIEF_REVIEW_READY`，由 Chief 批准、退回或继续派发。项目最终完成仍必须由操作者确认。

兼容模式 `all_reports` 可恢复每份里程碑/最终交接都由操作者批准的旧行为；此时 `report_approval_required` 为 `true`。无论采用哪种模式，汇报批准都不会自动授权删除、发布、生产变更、支付、外发消息或扩大权限。

### 主席负责制

启用 `governance_model.mode = chair_led_cabinet` 后，操作者只保留最终目标、重大产品路线、视觉选择、高影响操作、Chief 任免/暂停及项目最终验收等权力。项目 Chief 对日常行政、岗位管理、普通验收、一次限界返修和安全范围内的阶段推进负全责；只读复核者只有证据核验权。

普通岗位使用 `CHIEF_REVIEW_READY` 向项目 Chief 汇报。非视觉法定例外使用 `CHAIR_BRIEF_READY` 交给“一人之下”，由它压缩、去重后才能向操作者发出 `USER_ACTION_REQUIRED`；视觉决定仍只进入创意总监。TODO 只扫描这两个权威入口。等待决定只冻结受影响的写入面，其他安全路线必须继续。

可选启用 `governance_model.continuation_policy` 后，项目 Chief 必须选择证据最强、在范围内且安全的继续路径并直接执行。只要这种路径仍存在，就不把停止、保留失败状态或延期列成需要操作者选择的并列方案；普通失败继续由 Chief 通过限界诊断、修复和复检负责。只有继续本身需要新增权限或创建新 Chief 时才报备。该规则不会授权高影响操作、绕过视觉门、隐藏安全证据、改变写入权或扩张已确认目标。

### 产品分类与产品发现门

初始使命、目标边界和验收确认后，Chief 必须先写入 `.chief-of-staff/product-discovery.json`。创建或实质改变产品、服务、代码、设计、内容资产或其他需验收交付物的项目属于 `deliverable_project`；仅同步或推送既定变更、会议总结、备案/流程推进、只读审计或汇总可列为 `coordination_only`，但必须记录具体豁免理由。协调型项目一旦扩展到产品创作或实质交付，豁免立即失效并重新分类。

交付型项目必须任命一个 depth-2 产品经理阶段负责人。产品经理不是 Chief，也不形成第二控制面；其四条必备证据线是项目立项、需求分析、市场调研和非绑定的架构可行性。临时 helper 固定为 depth 3，不能继续委派或创建长期岗位；运行时没有 subagent 时，产品经理可在单任务中分别完成四条证据线，但必须记录运行限制，不能省略产出。综合结论覆盖目标/非目标/指标、市场与竞品、用户与痛点、政策和商业可行性、需求分层与剔除依据、用户画像、技术约束、风险/证据缺口、推荐 MVP 和可追溯证据索引。

产品门通过前，只能进行目标澄清、只读发现、需求研究和可逆规划；创建或启动工程、设计、内容生产等岗位前必须运行初始化器的 `--check`，非零结果就是硬阻断。不得伪造访谈、问卷或市场数据；真人外联、问卷发送、付费数据、受限访问和其他高影响操作仍需独立授权。架构线只提供可行性、接口、约束和风险，不替代后续技术负责人的最终架构权；体验目标可记录，但可点击 NON-FINAL 视觉选项仍只送创意总监。旧项目缺字段时迁移为 `legacy_unclassified/legacy_pending`，不会伪造已通过，并必须在下一次新增生产阶段前完成分类和必要产品门。

### 目标闭环与主动推进

初始化后，Chief 会先根据项目上下文提出最终目标、交付物、验收标准、非目标和约束，请你确认或修改。新项目在你明确确认前只允许为澄清目标进行有限的只读侦察。旧项目迁移时允许已经开始的非高影响任务完成，但不会派发新任务或进入新阶段。确认结果和逐项验收证据保存在 `project-plan.json`。

目标确认后，Chief 将工作拆为阶段，并确保未完成项目始终满足以下之一：有岗位正在排队、工作或等待处理；正在等待你的具体决定；或者存在有证据且有解除条件的阻塞。如果本阶段岗位全部结束但最终验收仍未满足，Chief 会自动创建并推进下一阶段，而不是只回答“当前无待审批事项”。

默认层级为 `Chief → 阶段负责人 → 执行岗位/临时 subagents`。阶段负责人可以在授权范围内创建执行岗位；临时 subagents 不能继续创建长期岗位。需要第四层时，Chief 必须先说明原因、期限、岗位结构和不扩层的影响并向你申请。

未完成项目的 Chief 汇报固定包含最终目标、当前阶段、已验证进展、正在工作的岗位、距最终交付的差距和下一检查点。只有全部最终验收标准都有证据时才能宣布项目完成。

### 有效吞吐、创意与部署

`effective_throughput` 以已完成且有证据的验收为中心。默认至多两个无共享写入面的独立阶段并行；每个检查点必须关联具体验收证据，连续两个检查点无证据时，Chief 停止该线路并自查目标、范围、依赖、写入权、验收方法和阻塞原因。

只有最终目标已确认、验收可验证且没有待处理人工门时才可使用 `/goal`。创意总监在北京时间每天 11:00 和 20:00 执行有证据的主动扫描，最多保留一条待定创意建议；同时可作为唯一视觉审阅中心接收项目预览并回传妈妈原话。除登记过的视觉决定回传外，它只读其他项目、不主动干预、不改文件。偏好证据分为明确偏好、一致模式和单次假设；新项目建议至少需要两个不同项目的明确偏好或一致模式证据，并包含目标用户、最小验证、成功阈值和停止条件。

当云部署工作被明确纳入范围时，应在独立 registry 中登记目标与证据；该记录是库存与审计记录而非执行凭证。生产部署、生产变更、发布或回滚均须在操作前单独取得明确用户批准。

### 全局上下文无损接续

仓库同时提供 `context-handoff` Skill。它只使用最新输入 token 与模型上下文窗口的比值：75%刷新检查点，85%在安全边界创建 `原对话名｜续N`，95%进入紧急迁移。累计 token 和账户限额不会被误当成上下文占用。

项目迁移包保存在 `.codex/context-migrations/`，无项目任务保存在 `~/.codex/context-migrations/`。新对话必须返回 `MIGRATION_READY` 并核对目标、审批、任务关系、写入权、Git 状态、证据、下一步、暂停状态和全局规则。若原任务绑定自动化，迁移包还必须逐项记录精确 ID、名称、类型、目标 task ID、状态、schedule、prompt SHA-256 和通知策略；在接管、切换权威入口或归档 predecessor 前，复用并重绑到精确 successor task ID，再用 live automation view 核验。配置引用和 update receipt 不是证明。缺失时仅在既有授权内建立一个最小等价项；禁止同职责 ACTIVE 重复，且必须保持 schedule、prompt 语义、通知策略和范围。任一不一致均记录 `automation_rebind_failed`、返回 `MIGRATION_BLOCKED` 并保持 predecessor active/unarchived。

普通未获批 Chief 的 successor 不继承置顶，也不因未置顶触发替换。只有 mandatory 或妈妈批准的 optional lineage，在完成 bundle parity、automation parity 与适用的 pin parity 后，才可接管；置顶 successor 仍须用 fresh `list_threads` 独立确认精确 task ID 位于 `pinnedThreads`，`pinned: true` 只表示操作已受理。失败则记录 `pin_verification_failed`，不接受接管，并按安全边界的同项目单 replacement 流程处理。旧对话不会删除，不得重复 Chief、改变范围、恢复暂停或绕过审批；已归档 predecessor 的历史自动化异常只修复 successor 绑定，不反向解档、删除或重复创建。

### 当前限制

- 第一版不修改 Codex 客户端界面；只在宿主已提供阻塞式选择面板时调用它，否则使用对话或 CLI 配置。
- 关闭 Codex 可能会停止正在运行的任务；持久状态保存在项目文件和 Codex 任务历史中。
- 当前不安装 AWS CLI Agent Orchestrator 等外置控制台；`control-plane.json` 仅预留未来适配入口。

<a id="english"></a>

## English

[Go to 中文](#中文)

### What it does

Chief of Staff gives each Codex project a single user-facing control point. The main task is named dynamically as `Chief of <project name>`, for example `Chief of Personal Web`. An ordinary Chief starts unpinned; only central roles and operator-approved optional slots enter the pin workflow. You talk to that main task; it decomposes the objective, creates durable tasks when separate long-lived context is useful, collects structured handoffs, and consolidates the final report.

Each durable task can use installed Skills automatically and can summon temporary subagents for bounded research, review, testing, or discussion.

### Key features

- A distinguishable main task name for every project: `Chief of <project name>`.
- Ordinary Chiefs default to unpinned. Only the five central roles—general office, TODO, Creative Director, context migration monitor, and Testing Director—and operator-approved optional product Chief slots require pins and controlled inheritance. The Testing Director owns cross-project quality policy and evidence review, not a second operator-facing approval path or automatic project write access. An operation receipt is not evidence; an eligible lineage needs the exact task ID in a fresh `pinnedThreads` listing before authority transfer.
- `exception_only` review by default: the Chief accepts routine milestone and role-final handoffs, while enumerated exceptions and final project completion go to the operator; simultaneous updates are collected in a batch.
- Mandatory user confirmation of the final goal, deliverables, and acceptance criteria before implementation.
- Mandatory post-confirmation classification: deliverable projects must pass a four-lane, depth-2 Product Manager discovery gate before production roles are created or started. Pure synchronization/push, meeting-summary, filing/process, or read-only aggregation work may be exempt with a recorded reason and must be reclassified if scope expands.
- Coverage-first capability discovery at project startup: scan built-in and installed capabilities, available plugins and Skills, official documentation, maintained open-source projects, and reusable external configuration before closed-world implementation. Refresh the scan against the chosen stack before production, and route test-related candidates to the Testing Director. Payment, permission expansion, production actions, and other protected changes remain separately approved.
- Continuous phase dispatch until final acceptance, with a three-level management hierarchy by default.
- One accountable main task for user communication.
- Durable tasks named `Role｜Work outcome`.
- Temporary subagent meetings inside durable tasks.
- Luna for read-only exploration, Terra as the sole implementation writer, and Sol for high-risk arbitration by default.
- One writer per file, external record, branch, deployment target, or deliverable.
- Structured handoffs that separate verified facts, inference, open questions, risks, and next steps.
- Explicit user approval before deletion, production changes, releases, payments, external messages, or permission expansion.
- An optional pause-title policy adds `已暂停｜` only after an explicit pause and removes it after an explicit resume; idle, blocked, and awaiting-user states do not trigger it.
- Optional American-English coaching can cover work and casual chat with written, spoken, and idiom text. `host_builtin` relies on the client's voice/read-aloud control and generates no files; only opt-in `auto` or `macos_say` offline mode creates separate written and spoken `.m4a` attachments.
- Persistent project state with a reserved adapter seam for a future external control plane.
- Effective throughput: at most two independent phase lanes, checkpoint evidence, and a stop/self-check after two evidence-free checkpoints.
- `/goal` only after a confirmed, testable goal with no human gate; durable goals never bypass protected-action approvals.
- Evidence-backed Creative Director scans at 11:00 and 20:00 Beijing time, with no more than one pending creative recommendation. When the visual gate is enabled, it also becomes the only operator-facing visual review hub: it receives project preview packets and relays only the operator's exact decision back to the source Chief.
- An independent cloud deployment registry; a registry record never authorizes production work.
- An optional human visual-selection gate: projects submit clickable previews only to the pinned `Chief of Creative Direction｜创意总监`; project Chiefs, roles, the general Chief task, and TODO must not duplicate the request, and no unselected option may become the final version.
- An optional pinned, cross-project unanswered-Chief TODO with configurable reminders; disabling it stops all reminder runs.

### Token cost and intended users

Chief of Staff is an orchestration layer built around durable context, role separation, independent review, and proactive follow-up. It can therefore use substantially more tokens than a comparable single-agent conversation. Every durable task and subagent performs its own model and tool work; additional parallel roles, longer contexts, and repeated review cycles generally increase that overhead. OpenAI's documentation likewise notes that subagent workflows consume more tokens than comparable single-agent runs. [OpenAI Subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)

- **Enterprises and mature teams: recommended for direct use.** It fits long-running cross-functional work that benefits from ownership boundaries, approval records, evidence trails, and consolidated reporting. Configure concurrency limits, model routing, phase budgets, and stopping conditions.
- **Individuals and beginners: enable it selectively.** Do not start the full hierarchy for a simple task. Prefer the `core` preset, one phase/one writer, and lower-cost models. For coding, diagnosis, review, and evidence-backed execution, explicitly invoke this repository's original `$kai-lean-execution` to reduce redundant investigation, repeated planning, and log-heavy reporting without narrowing the goal or skipping acceptance. Use `context-handoff` for actual long-conversation migration. The Skill promises no fixed token-saving percentage.
- **Token burn is not a success metric.** Evaluate delivered artifacts, verification evidence, blocker resolution, and final acceptance. A token-reduction Skill must not replace human approvals, complete validation, or retention of auditable source records.

### Requirements

- A current Codex desktop app, Codex CLI, or IDE extension with Skills and subagents enabled.
- Python 3.9 or newer for the project initializer.

### Install

Clone this repository, then copy or symlink it into your personal Codex Skills directory:

```bash
git clone https://github.com/rong2qi/chief-of-staff-codex.git chief-of-staff
cp -R chief-of-staff ~/.codex/skills/chief-of-staff
cp -R chief-of-staff/context-handoff ~/.codex/skills/context-handoff
cp -R chief-of-staff/kai-lean-execution ~/.codex/skills/kai-lean-execution
```

Open a new Codex task after installation. Codex normally detects Skill changes automatically; restart it if the Skill does not appear.

### First-use preference setup

Cloning and copying the Skill never runs setup by itself. Setup begins only when you enter one of these prompts:

```text
$chief-of-staff configure my preferences
$chief-of-staff initialize this project
```

If no profile exists, a Codex host with a native blocking selection panel presents three questions in one form:

1. Preset: `Core Chief`, `Operator-controlled + bilingual coaching`, or `Custom`. The form also explains that full Chief coordination is recommended for enterprises and mature teams with explicit concurrency/model/phase budgets, while individuals and beginners should prefer Core Chief, one phase/one writer, and lower-cost routing.
2. Salutation: neutral, `妈妈`, or a custom value.
3. Data location: the default personal directory, an external/custom absolute path, or the current project only.

Individuals and beginners also see this repository's original, explicit-only `$kai-lean-execution` recommendation; onboarding never invokes it automatically or injects extra agents into the current task. Codex previews the enabled rules, destination, voice delivery, and fallback behavior, then writes only after a final Apply confirmation. Custom mode opens a second form for visual approval, casual-chat coaching, written/spoken/idiom notes, built-in host voice or offline audio attachments, voice and rate, pause-title behavior, TODO reminders, and reminder cadence. A CLI or IDE without the native panel asks the same questions conversationally; it does not simulate a pop-up.

For deterministic non-interactive setup:

```bash
python3 ~/.codex/skills/chief-of-staff/scripts/configure_preferences.py \
  --preset operator-controlled-bilingual \
  --scope global \
  --salutation Operator \
  --audio-provider host_builtin \
  --data-root /Volumes/ExternalDrive/chief-data
```

A custom data root must already exist. A missing or unwritable external disk fails safely with no local fallback. Global preferences are configured once and inherited by future projects; use `$chief-of-staff reconfigure my preferences` to run onboarding again. The public `core` preset leaves every personal rule disabled.

The unified profile controls chair-led governance and continuation policy, the single-hub visual gate, American-English coaching and casual-chat coverage, voice delivery, salutation, pause-title prefix, and reminder schedule. The configurator replaces only a marked managed block in `AGENTS.md`. The bilingual preset defaults to `host_builtin`: the Skill supplies written, spoken, and idiom text while the Codex/ChatGPT client owns voice/read-aloud playback; no audio files are generated and per-sentence autoplay is not promised. Only an explicit `auto` or `macos_say` offline choice creates separate content-addressed `.m4a` attachments for enabled written and spoken text; missing storage or renderer support safely returns text only.

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
  "pin_primary_task": false,
  "report_review_mode": "exception_only",
  "report_approval_required": false,
  "governance_model": "standard",
  "operator_role": "operator",
  "continuation_policy": "standard",
  "ordinary_failure_policy": "bounded_repair_cycle",
  "continuation_escalation_policy": "existing_approval_boundaries",
  "project_classification_policy": "classify_after_goal_confirmation",
  "deliverable_product_discovery_policy": "required_before_production",
  "production_start_policy": "deny_until_product_discovery_passed_or_coordination_exempt",
  "product_discovery_state_file": ".chief-of-staff/product-discovery.json",
  "legacy_allowlist_digest": null,
  "require_goal_confirmation": true,
  "durable_goal_enabled": true,
  "execution_mode": "effective_throughput",
  "max_parallel_phase_lanes": 2,
  "no_evidence_checkpoint_limit": 2,
  "max_management_depth": 3,
  "auto_advance_low_impact": true,
  "proactive_follow_up": true,
  "visual_selection_gate": "disabled",
  "visual_review_hub_title": "Chief of Creative Direction｜创意总监",
  "durable_child_scope": "same_project",
  "archive_completed_child_tasks": true,
  "projectless_child_policy": "temporary_subagents",
  "peer_coordination_enabled": true,
  "peer_contact_policy": "registered_same_project",
  "subagent_meetings_enabled": true,
  "max_meeting_participants": 3
}
```

At initialization, `.chief-of-staff/product-discovery.json` is `pending/unclassified`; the initializer never guesses the project type. A coordination-only example after goal confirmation is:

```json
{
  "classification_status": "classified",
  "project_classification": "coordination_only",
  "product_manager_required": false,
  "exemption_reason": "Only synchronize and push an already-approved change",
  "gate_status": "exempt"
}
```

A deliverable project uses `deliverable_project`, appoints the Product Manager, and can reach `gate_status: passed` only after all four evidence lanes are complete.

The Skill reads `primary_task_title` and renames the current main task to that exact value. Ordinary Chiefs default to unpinned (`pin_primary_task=false`), and that is not a defect. Only the general office, TODO, Creative Director, context migration monitor, and Testing Director are mandatory pins. An optional product Chief requires a general-office pack of at most three candidates, read-only TODO checks of identity, currentness, duplication, evidence freshness, capacity, and lineage, then the operator's explicit appointment and pin approval. The default optional limit is six; manual non-Chief pins are protected. Historically retained slots are called grandmothered optional Chiefs; they remain unchanged pending value review but do not inherit automatically. Full capacity yields only a paired replacement recommendation. Pin approval does not confirm the goal or authorize engineering, design, or production; the Product Manager and four-lane discovery gate remains mandatory. Only a mandatory or approved lineage may create one replacement after a safe core handoff candidate; automation parity and a fresh exact-ID `list_threads` check must pass before final `MIGRATION_READY`, takeover, and predecessor archival. A `pinned:true` receipt is not proof.

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
├── pin-state.json
├── project-plan.json
├── product-discovery.json
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
    ├── Product Manager｜Discovery and charter (required for deliverables)
    │   ├── Project initiation subagent
    │   ├── Requirements analysis subagent
    │   ├── Market research subagent
    │   └── Architecture feasibility subagent
    ├── Technical Lead｜Decide architecture
    │   ├── Security subagent
    │   └── API subagent
    └── Implementation Lead｜Deliver the change
        └── Verification subagents
```

Durable Codex tasks retain visible, independent context. Temporary subagents handle bounded work and report to their parent task. The main task remains responsible for reconciling evidence and reporting to the user.

### Project space and Recents

Before creating a durable role, the Chief resolves its Codex `projectId`, creates the child against the same project target, and records that ID in the task registry. If the Chief is not in a saved project, it defaults to temporary subagents and asks the user to select or save a project only when separate durable history is necessary.

Codex treats durable tasks as independently resumable tasks, so active project roles may still appear in Recents. That shared view is useful for surfacing running, failed, and needs-attention states without opening every project. This Skill therefore uses a lifecycle policy: active or actionable roles remain visible; under `exception_only`, the Chief archives a routine child only after reviewing its final handoff, recording evidence, and confirming that no retry remains. Final project completion still requires the operator. Archiving is reversible and preserves the task ID, result summary, and project registry record.

### Peer coordination and multi-agent meetings

The Chief creates symmetric `coordination_with` edges in `task-registry.json` for same-project roles with a real dependency. Registered peers may directly exchange structured messages about interfaces, evidence, dependencies, or handoffs, then copy the outcome or unresolved conflict back to the Chief. Routine coordination needs no human approval and cannot create a competing project plan.

Every durable role may convene a temporary subagent meeting with up to three participants by default. A meeting has one question, non-overlapping roles, evidence inputs, a stopping condition, and a synthesis owner. Participants are read-only by default and cannot create durable roles; if implementation is included, exactly one participant owns the write surface. The parent waits for all results, reconciles them by evidence, and sends one concise outcome to affected peers and the Chief.

### Unanswered-Chief TODO and reminders (optional)

Reminders are one personal, cross-project service rather than one automation per Chief. Only when `reminders.enabled` is `true` does the Skill create or reuse a pinned `TODO｜待回复 Chief 汇总` thread. It includes only Chiefs that explicitly await approval, confirmation, a decision, more information, or a permission choice and have no later resolving user reply. For visual selections, only `Chief of Creative Direction｜创意总监` is authoritative; copies in project Chiefs, roles, the general Chief task, and retired hubs are excluded, and multiple visual IDs are grouped under that one task. Merely opening or reading a thread does not clear an item.

### Visual decisions go only to the Creative Director

With `visual_selection_gate` enabled, a project Chief creates or organizes clickable NON-FINAL previews, then submits the stable decision ID, differences, evidence, and impact only to the single pinned `Chief of Creative Direction｜创意总监`. The Creative Director may hold multiple incoming visual decisions and batches newly changed items into one concise review message. The one-pending-recommendation limit applies only to proactive creative suggestions, not to project-submitted visual approvals.

The Creative Director cannot choose for the operator, implement the design, install a build, or modify the source project. After an explicit operator decision, it relays only the exact wording, decision ID, and boundary to the source Chief. If the operator has not replied, the Creative Director waits without repeated nudges; the shared TODO later discovers that one task instead of every project reminding separately.

The example preset uses every Beijing-time hour from 09:00 through 18:00 inclusive, plus 22:00; timezone, daytime window, interval, and additional times are configurable. Saving a preference does not create an automation by itself: the Skill still uses Codex's scheduled-task interface to create or update it. Disabling pauses every automation recorded by the policy, producing no scan runs or notifications while preserving the TODO thread and identifiers for later re-enablement.

### Report approval workflow

The default `report_review_mode` is `exception_only`. Roles still return a unique report ID, evidence, risks, and next steps, but the project Chief reviews routine progress and role-final handoffs against the execution contract instead of asking the operator. The Chief checks scope, exclusive write ownership, acceptance evidence, tests, conflicts, and protected-action boundaries, then records its decision basis in `approval-queue.json`.

Only goal confirmation, material product choices, visual choices, protected actions, safety issues, scope or ownership conflicts, failed or unverifiable work, depth expansion, and final project completion reach the operator. Exceptions use `USER_ACTION_REQUIRED`; routine role handoffs use `CHIEF_REVIEW_READY`, and the Chief approves, requests changes, or advances the work. Final project completion still requires the operator.

Compatibility mode `all_reports` restores the previous behavior in which every milestone/final handoff requires operator review and sets `report_approval_required` to `true`. In either mode, report approval never authorizes deletion, release, production changes, payments, external messages, or permission expansion.

### Chair-led cabinet governance

With `governance_model.mode = chair_led_cabinet`, the operator retains final-goal, material product-direction, visual-selection, protected-action, Chief appointment/pause/removal, and final project acceptance powers. Project Chiefs are accountable for routine administration, role management, ordinary acceptance, one bounded repair cycle, and safe phase advancement. Read-only verifiers have evidence authority only.

Routine roles use `CHIEF_REVIEW_READY`. Non-visual statutory exceptions use `CHAIR_BRIEF_READY` to the general office, which deduplicates and compresses them before emitting `USER_ACTION_REQUIRED`; visual decisions remain exclusive to the Creative Director. TODO scans only those two authoritative hubs. Waiting freezes only the affected write surface while independent safe work continues.

When `governance_model.continuation_policy` is enabled, each project Chief executes the strongest evidence-backed safe in-scope continuation. Stopping, preserving a failed state, and delaying are not peer options while such a path exists. Only a continuation that itself needs a new permission or a new Chief is escalated. Protected actions, visual gates, safety disclosure, write ownership, and the confirmed goal remain unchanged boundaries.

### Product classification and discovery gate

After the initial mission, goal boundary, and acceptance contract are confirmed, the Chief records classification in `.chief-of-staff/product-discovery.json`. A project that creates or materially changes a product, service, code, design, content asset, or another acceptance-tested deliverable is a `deliverable_project`. Synchronizing or pushing an already-decided change, summarizing a meeting, advancing a filing/process, or performing read-only audit/aggregation may be `coordination_only`, but requires a concrete exemption reason. Any expansion into product creation or material delivery invalidates the exemption and triggers reclassification.

A deliverable project appoints one depth-2 Product Manager phase lead. The Product Manager is not a Chief and does not create a second control plane. Its four required evidence lanes are project initiation, requirements analysis, market research, and non-binding architecture feasibility. Temporary helpers are depth 3 and cannot delegate again or create durable roles. If subagents are unavailable, the Product Manager may complete all four lanes in one task only with a recorded runtime limitation and separate evidence for every lane. The synthesis covers the charter, goals/non-goals/metrics, market and competitors, users and pain points, policy and business feasibility, prioritized and rejected requirements, personas, technical constraints, risks and evidence gaps, a recommended MVP, and a traceable evidence index.

Before the gate passes, only goal clarification, read-only discovery, requirements research, and reversible planning are allowed. The initializer's `--check` is a required fail-closed preflight before creating or starting engineering, design, content-production, or other production roles. Interviews, surveys, and market facts must never be invented; outreach, survey delivery, paid data, restricted access, and every protected action retain separate approval gates. Architecture discovery is advisory and cannot bind the later Technical Lead. Experience goals may be recorded, but clickable NON-FINAL visual options remain exclusive to the Creative Director. Existing projects missing these fields migrate to `legacy_unclassified/legacy_pending`, never to a fabricated pass, and must classify before adding the next production phase.

### Goal closure and proactive progression

After initialization, the Chief drafts the final goal, deliverables, acceptance criteria, non-goals, and constraints from available project context and asks you to confirm or revise them. A new project permits only bounded read-only discovery before explicit confirmation. During migration, already-running non-high-impact tasks may finish, but no new task or phase starts. The confirmed contract and criterion-level evidence live in `project-plan.json`.

Once confirmed, the Chief divides the work into phases. Until final acceptance, the project must have an active, queued, or attention-needed role; be waiting for an exact user decision; or be blocked with evidence and a release condition. If every role in a phase stops while final acceptance remains unmet, the Chief dispatches the next safe in-scope phase instead of replying only that no approval is pending.

The default hierarchy is `Chief → Phase Lead → Execution Role/temporary subagents`. Authorized phase leads may create execution roles; temporary subagents cannot create durable roles. A fourth management level requires the Chief to request approval with the reason, duration, proposed structure, and impact of refusal.

Every unfinished-project report includes the final goal, current phase, verified progress, active roles, remaining delivery gap, and next checkpoint. The Chief may declare completion only when every final acceptance criterion has supporting evidence.

### Global loss-aware context rollover

The repository also includes `context-handoff`. It uses only newest input tokens divided by the model context window: checkpoint at 75%, create `Original title｜Continuation N` at a safe boundary at 85%, and prioritize migration at 95%. Cumulative and account usage are ignored.

Project bundles live in `.codex/context-migrations/`; projectless bundles live in `~/.codex/context-migrations/`. A successor must return `MIGRATION_READY` and match goals, approvals, task graph, write ownership, Git state, evidence, next action, pause state, and global instructions. For each task-bound automation, the bundle records exact ID, name, kind, target task ID, status, schedule, prompt SHA-256, and notification policy. Before takeover, authority switching, or predecessor archival, reuse and rebind it to the exact successor task ID, then verify it in a fresh live automation view. Configuration references and update receipts are not proof. Only proven live absence plus existing authorization permits one minimal equivalent; duplicate ACTIVE same-duty automations are forbidden, and schedule, prompt semantics, notification policy, and scope remain unchanged. Any mismatch records `automation_rebind_failed`, returns `MIGRATION_BLOCKED`, and keeps the predecessor active and unarchived.

An ordinary unapproved Chief does not inherit a pin and never enters replacement merely because it is unpinned. For a mandatory or operator-approved optional lineage, bundle parity, automation parity, and applicable pin parity must all pass. A fresh `list_threads` exact-ID check remains mandatory; `pinned: true` is only an operation receipt. A failed check records `pin_verification_failed` and denies takeover. Predecessors remain recoverable; migration cannot create duplicate Chiefs, change scope or pause state, or bypass approval. Historical automation repair after archival never unarchives/deletes the predecessor or duplicates the task or automation.

### Current limits

- Version 1 does not modify the Codex client UI. It uses a native blocking selection panel only when the host already provides one, with conversational and CLI fallbacks.
- Closing Codex may stop active work; persistent coordination state is stored in project files and Codex task history.
- An external control plane such as AWS CLI Agent Orchestrator is not installed. `control-plane.json` reserves a future integration point.

## Repository contents / 仓库内容

- `SKILL.md`: Skill routing and operating instructions / Skill 路由与操作说明。
- `scripts/init_project.py`: safe project initializer and validator / 安全的项目初始化与校验脚本。
- `scripts/configure_preferences.py`: idempotent preference onboarding / 幂等偏好配置器。
- `scripts/render_english_audio.py`: opt-in offline attachment renderer for `auto`/`macos_say`; never used by `host_builtin` / `auto`、`macos_say` 的可选离线附件渲染器，`host_builtin` 不调用。
- `assets/project-template/`: generated project contract and agent profiles / 项目契约与角色配置模板。
- `assets/operator-preferences.example.json`: privacy-safe core defaults / 隐私安全的核心默认偏好。
- `assets/presets/`: opt-in preference presets / 可主动启用的偏好预设。
- `references/`: coordination protocol, enforceable product-discovery governance, and persistent state schema / 协调协议、可执行产品发现治理与持久状态结构。
- `references/operator-preferences.md`: onboarding, schema, and privacy behavior / 首次配置、结构与隐私行为。
- `assets/reminder-policy.example.json`: optional personal reminder policy example / 可选的个人提醒策略示例。
- `agents/openai.yaml`: Codex UI metadata and implicit invocation policy / Codex 界面元数据与自动调用策略。
- `context-handoff/`: global context checkpoint and verified rollover Skill / 全局上下文检查点与校验接续 Skill。
- `kai-lean-execution/`: original explicit-only lean execution Skill / 原创、仅显式调用的精简执行 Skill。

# Chief of Staff for Codex / Codex 幕僚长

![Chief of Staff — 像素少女统筹工作室 / Pixel-art coordination studio](assets/readme/banner.png)

## v3.0.0：目标驱动薄执行层 / Goal-driven thin execution layer

本地 v3.0.0 候选把 Chief 核心收敛为一个从既有状态与新鲜观察投影的
Goal Record、一次只选择一个动作的 Next Action Loop，以及绑定真实观察的
Acceptance Claim/Proof。交付宿主与固定只读参考源分别记录；本地修改、commit、
push、release/deploy、生产变更和交付仍是互不继承的独立效果。真实用户路径可用时，
组件绿灯不能替代它；策略或准入函数返回成功也不会凭空创造宿主能力。

The local v3.0.0 candidate declares contract schema `2`,
`WORK_EXECUTION_V1`, and `GOAL_LOOP_V1`. New projects receive the Goal Loop
field; v2 projects adopt it only through an explicit preview/apply sync. The
active entry is intentionally small and loads rules by observable action
trigger. All v2 behavior remains byte-preserved at
[`references/chief-v2-compat.md`](references/chief-v2-compat.md), while the v3
contract and executable seam live in [`V3_SPEC.md`](V3_SPEC.md),
[`V3_ACCEPTANCE.md`](V3_ACCEPTANCE.md), and
[`scripts/goal_loop.py`](scripts/goal_loop.py). This candidate is not a tag or
published release; installation, project migration, commit, push, and release
remain separate authorized actions.

## v2.0.2：证据复用、风险驱动、非阻塞测试 / Evidence-aware, risk-based, non-blocking Testing

让证据帮助工作向前走。꒰ঌ(っ˘꒳˘ｃ)‪໒꒱

Testing 由新增风险触发，而不是由新代码、commit、candidate、阶段或集成本身触发。冻结且通过的证据可复用：
无关范围继承 `INHERITED_PASS`，受影响范围进入 `RETEST_REQUIRED`，首次组合风险只做最小
`INTEGRATION_ONLY` smoke。L0 只做确定性本地验证；L1 默认本地；L2 只送新增风险 delta；
L3 或 `SYNC_TESTING_REQUIRED` 只阻塞对应危险动作。`TESTING_PENDING` 与 Testing 基础设施故障
不会让无关工作 idle；ACK/READY/STARTED 等遥测不会进入 reasoning 主链，同一 delivery 最多自动重试一次。

The additive evidence format retains original gate authority, candidate SHAs,
scope, Git snapshots, dependency fingerprints, evidence identity/time/result and
risk scope. Project schema stays **2** and v1 frozen evidence remains readable.
See [the evidence workflow](references/testing-evidence.md) and
[risk-based control](references/testing-control.md). Release-specific adoption,
dogfood and rollback notes are in [v2.0.2 migration notes](docs/releases/v2.0.2.md).

Chief regression command (Python 3.11+): `python3 -m unittest discover -s tests`.

新项目默认使用 `WORK_EXECUTION_V1`；旧项目必须由原 Chief 明确重读并采用一次。当前 Chief 可以直接高效执行，`DIRECT` 是执行方式，不是岗位。按当前工作决定发现深度，按风险与证据决定自检或独立复核；详见 [通用工作执行规则](references/work-execution.md)。下文的项目级产品门适用于旧项目；V1 新产品仍保留完整产品经理和四路发现要求；安全、授权、目标和适用的未决产品要求始终保留。

New projects default to `WORK_EXECUTION_V1`; an existing Chief explicitly rereads and adopts it in place. The Chief may execute directly when efficient; `DIRECT` is a mode, not a role. Current work determines discovery depth, while risk and evidence determine review independence. See [work execution](references/work-execution.md). Legacy whole-project gates apply without V1 adoption; V1 new-product work still requires the full Product Manager and four-lane workflow. Safety, authorization, goal boundaries, and applicable unresolved product requirements remain binding.

<a id="chief-202-installation-and-explicit-fleet-sync"></a>

## Chief 2.0.2 安装与显式批量同步 / Installation and explicit fleet sync

先预览、再同步，保留原有工作与回滚路径。(   ᵒ̴̶̷̤-ᵒ̴̶̷̤ )

`chief-version.json` declares Chief `2.0.2`, contract schema `2`, and `WORK_EXECUTION_V1`. New and explicitly synced projects have a thin managed `AGENTS.md` entry generated from [chief-project-entry.md](assets/chief-project-entry.md), plus `.chief-of-staff/chief-lock.json` recording the exact source commit and managed-file hashes. Generic logic remains in the pinned Chief source. The old full project template is retained only for compatibility recognition/tests. Put project-specific commands, business constraints, and stricter limits in user-owned `.chief-of-staff/project-overrides.md`; sync does not overwrite it. Overrides cannot expand permissions or waive validation.

新版采用单一真源：固定 Chief 版本和提交，项目只留轻入口及受控的专属覆盖。旧 Chief 在原任务中明确重读和采用即可，不必重启或新建任务。新产品仍须完整产品经理与四路发现流程；明确的既有操作、修复及受影响变更按当前工作处理。版本锁只证明来源和检测冲突，不是授权。

Use a dedicated, clean source checkout at stable tag `v2.0.2`. This release's sync command verifies that source HEAD is exactly the tag commit and rejects local source changes. It does not follow floating `main`. Replace `/path/to/chief-source` consistently with your chosen installed Skill/source directory:

```bash
git clone --branch v2.0.2 --single-branch https://github.com/rong2qi/chief-of-staff-codex.git /path/to/chief-source
```

For an existing clean source checkout, update the fixed reference without discarding local changes:

```bash
git -C /path/to/chief-source fetch origin tag v2.0.2
git -C /path/to/chief-source switch --detach v2.0.2
```

If Git reports local changes or a tag conflict, resolve them explicitly; do not force/reset/stash as part of sync. `--source` selects the fixed implementation and assets even when the invoking script lives elsewhere.

Copy [projects.example.json](assets/projects.example.json) to a user-maintained manifest, adjust paths, and mark the projects selected for this migration `pinned: true`. Relative project paths resolve from the manifest directory. Here `--pinned` filters that manifest field; it does not scan the sidebar, change task pins, or discover other projects. Create the report destination directory before using `--report`; the command does not create parent directories. The recommended batch command is:

```bash
python3 /path/to/chief-source/scripts/chief_sync.py fleet-sync --source /path/to/chief-source --projects /path/to/projects.json --pinned --report /path/to/reports/chief-sync.json
```

Preview the same selected projects before applying:

```bash
python3 /path/to/chief-source/scripts/chief_sync.py fleet-sync --source /path/to/chief-source --projects /path/to/projects.json --pinned --dry-run --report /path/to/reports/chief-sync-preview.json
```

Dry-run writes no project files, branches, commits, or worktrees; an explicitly requested report file is still written. For a single project use `sync --target`:

```bash
python3 /path/to/chief-source/scripts/chief_sync.py sync --source /path/to/chief-source --target /path/to/project --dry-run
python3 /path/to/chief-source/scripts/chief_sync.py sync --source /path/to/chief-source --target /path/to/project --report /path/to/reports/chief-project.json
```

Sync performs cheap Chief configuration/schema and migration checks. It does not run business tests, a complete project build, Android/native builds, or arbitrary project hooks. Chief's own fixture tests validate the migration tooling separately. Select any necessary project static check explicitly for its evidence value; sync does not infer or execute project commands. On an 8GB host prefer low concurrency and one Android/native heavy job at a time; a 16GB host still requires current resource observations before raising capacity. Fleet migration itself runs projects sequentially and is not a background scheduler.

Each result is `success`, `up_to_date`, `conflict`, `failed`, or `not_found`. A conflict in one project does not stop processing the other manifest entries. Inspect `changes`, `source_version`, `source_commit`, `branch`, `execution_path`, and `commit` when present. The process returns nonzero if any selected result is not successful/current. See the [written pressure review](docs/reviews/2026-09-09-workflow-pressure-review.md) for mechanisms and their limits. Example report excerpt (SHA placeholders below are not receipts):

```json
{
  "results": [
    {
      "name": "Example app",
      "target": "/projects/example-app",
      "status": "success",
      "source_version": "2.0.2",
      "source_commit": "<exact source SHA>",
      "branch": "chief/adopt-2.0.2",
      "execution_path": "/projects/example-app",
      "commit": "<exact migration SHA>",
      "validation_scope": "Chief schema and migration checks only; no business build/test"
    }
  ],
  "dry_run": false
}
```

A clean project switches to `chief/adopt-2.0.2` and receives a local migration commit. A project with unrelated business changes gets a separate Git worktree on that branch, leaving its original checkout and changes intact. Uncommitted Chief-managed changes require conflict review. A dirty project's successful result means its migration exists at `execution_path`; it does not mean the original branch adopted it. Review the migration diff and explicitly integrate its commit into the intended branch at a safe boundary. Sync never pushes, merges into the user's branch, or silently resolves their changes. Matching completed migrations are reused; a branch collision or drift is reported, not overwritten.

Managed instruction/hash conflicts, unrecognized legacy instructions, running/paused work, invalid retained state, source-pin mismatches, and independently frozen adapter gates need explicit resolution. Preserve business files, custom instructions, approvals, work history, failures, ownership, and stricter limits. Move only deliberately reviewed project-specific rules into the override file; do not copy generic rules there to bypass the pin. A transaction failure retains/reports recovery information and does not authorize continuing from a partially verified state.

To undo a committed migration in a clean checkout containing that exact commit, use its full SHA from the report:

```bash
python3 /path/to/chief-source/scripts/chief_sync.py rollback --target /path/to/project --commit FULL_MIGRATION_COMMIT_SHA --report /path/to/reports/chief-rollback.json
```

Rollback creates a revert commit; it does not delete the migration, reset history, push, or remove a worktree. It refuses dirty checkouts, non-migration commits, unmanaged changes, non-ancestor commits, or subsequent managed-file changes requiring manual reconciliation. If a migration is still only in its isolated worktree, point rollback at that `execution_path`. If an explicitly integrated commit has a different SHA, verify its migration metadata and use that exact local SHA. Continue the existing Chief after rereading the adopted pin; independent frozen adapters retain their required revalidation.

To move the Chief source itself back to the previous stable release without rewriting history, use a separate clean checkout or detach the existing clean source at `v2.0.1` (use `v2.0.0` only when that older policy is intentionally required), then run the same explicit project sync/rollback review. Never force-move a release tag.

> 通过一个统一负责的主任务、按职务命名的长期任务，以及临时子代理会议来协调 Codex 项目。
>
> Coordinate a Codex project through one accountable main task, durable role-based tasks, and temporary subagent meetings.

## 它能做什么 / What it does

**中文** <img src="assets/readme/anarrator/sparkle.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

Chief of Staff 为每个 Codex 项目提供一个统一的用户交互入口。主任务会根据项目名自动命名为 `Chief of <项目名>`，例如 `Chief of 个人web`。普通 Chief 初始化后默认不置顶；中央角色和妈妈批准的可选席位才进入置顶流程。你只需要和这个主任务交流；它负责拆解目标、创建需要长期独立上下文的任务、收集结构化汇报，并向你提供最终总结。

每个长期任务可以根据工作内容自动选择已安装的 Skill，也可以召集临时 subagents 完成范围明确的调研、评审、测试或讨论。

꒰ ՞ɞ̴̶̷̥⩊ɞ̴̶̷̥꒱֯

**English**

Chief of Staff gives each Codex project a single user-facing control point. The main task is named dynamically as `Chief of <project name>`, for example `Chief of Personal Web`. An ordinary Chief starts unpinned; only central roles and operator-approved optional slots enter the pin workflow. You talk to that main task; it decomposes the objective, creates durable tasks when separate long-lived context is useful, collects structured handoffs, and consolidates the final report.

Each durable task can use installed Skills automatically and can summon temporary subagents for bounded research, review, testing, or discussion.

## 核心能力 / Key features

**中文** <img src="assets/readme/anarrator/phone.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

- 每个项目拥有可区分的主任务名称：`Chief of <项目名>`。
- 普通 Chief 默认不置顶；只有 general office、TODO、创意总监、上下文迁移监控四个中央角色，以及妈妈批准的可选产品 Chief 席位，才需要置顶和受控继承。测试总监同样默认不置顶、只做跨项目质量证据审查，既不占 mandatory core，也不占 optional seat。操作回执不算证据，eligible lineage 只有在精确 task ID 出现在新的 `pinnedThreads` 查询中后才能切换权威入口。
- 默认采用 `exception_only`：Chief 验收普通岗位里程碑和最终交接，只有列明例外与项目最终完成才进入操作者批复；Chief 会批量收集同时到达的汇报，避免遗漏。
- 可选的“推荐即委托”规则只允许一般办公室直接放行唯一、证据完整、固定范围且非生产的 allowlisted 动作，并写入稳定审计标记；已委托或已解决事项不会进入 TODO。操作者专属决定、既有明确拒绝、失败、漂移和范围扩张不会被自动放行。
- 可选的“已批准决定直达”规则仅让 TODO 把稳定 ID 与操作者原话一次送达唯一、现任的来源 Chief，并异步留给一般办公室审计；TODO 没有批准或改写业务审批状态的权力，送达/ACK 不等于执行。未知、过期、重复或失败的送达只留证，不盲重发或换工具；新非视觉请求仍先走一般办公室，视觉仍只走创意总监。
- Chief 必须先与你确认最终目标、交付物和验收标准；未达成最终验收前持续分阶段推进。
- 未采用 V1 的旧项目在目标确认后必须分类：交付型项目先由 depth-2 产品经理完成四路产品发现与立项门，才可创建或启动生产岗位；纯同步/推送、会议总结、备案/流程推进或只读汇总可记录理由后豁免，范围扩展时立即重分类。
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
- 严格交付闭环必须由项目显式采用：`init_project.py --delivery-ledger-mode strict` 仅记录下次活跃回合、冷启动或既有授权 heartbeat 的对账义务；它不提供守护进程，也不声称会自动唤醒宿主。
- 连续执行也必须显式采用：完整批准包绑定已有计划、审批队列和唯一写入者；只有保留的真实进展可超过三轮。它不隐含远程、生产、付款、外发或扩权，也不会自行唤醒或派工。
- 默认采用 `effective_throughput`：最多两个互不冲突的阶段并行；每个检查点都要产生可验证证据，连续两个检查点无证据即停止并自查。
- 已确认、可验收且没有人工审批门的目标才可使用 `/goal`；长期目标不会绕过确认或高影响操作的单独审批。
- 创意总监在北京时间每天 11:00 和 20:00 执行有证据的主动扫描，而非空转目标；最多一条待定创意建议。启用视觉门时，它还是唯一面向操作者的视觉审阅中心：接收项目预览包、维护视觉待决队列，并只把操作者原话回传来源 Chief；除此以外只读、不主动干预、不修改项目文件。
- 云部署目标和证据登记在独立 deployment registry 中；登记不是授权，生产部署、生产变更、发布或回滚仍须在操作前取得明确用户批准。
- 可选的视觉人工门要求项目先提供可点击预览，并只提交给置顶的 `Chief of Creative Direction｜创意总监`；项目 Chief、岗位、“一人之下”和 TODO 不得复制同一视觉请求。操作者明确选择前，未选方案不得成为最终版本。
- 可选的暂停标题策略会在操作者明确暂停时添加 `已暂停｜`，明确恢复时移除。空闲、阻塞或等待批复不会被误判为暂停。
- 可选的美式英语教学可覆盖工作消息和闲聊，并提供书面、口语与地道用法文本。`host_builtin` 只交给客户端内置语音/朗读，不生成独立音频；仅主动选择 `auto` 或 `macos_say` 离线附件模式时才分别生成书面与口语 `.m4a`。
- 可选启用一个跨项目、置顶的 Chief 待回复 TODO，并按个人策略定时提醒；关闭后完全不运行提醒。

(  ᓀ⩊<)

**English**

- A distinguishable main task name for every project: `Chief of <project name>`.
- Ordinary Chiefs default to unpinned. Only four central roles—general office, TODO, Creative Director, and context migration monitor—and operator-approved optional product Chief slots require pins and controlled inheritance. The Testing Director remains ordinary/default-unpinned and coordination-only, occupying neither a mandatory core pin nor an optional seat. An operation receipt is not evidence; an eligible lineage needs the exact task ID in a fresh `pinnedThreads` listing before authority transfer.
- `exception_only` review by default: the Chief accepts routine milestone and role-final handoffs, while enumerated exceptions and final project completion go to the operator; simultaneous updates are collected in a batch.
- Optional recommended-action delegation lets the general office directly authorize only one evidence-complete, fixed-surface, nonproduction allowlisted action with a stable audit marker. Delegated or resolved work stays out of TODO; operator-only decisions, prior denial, failure, drift, and scope expansion never auto-delegate.
- Mandatory user confirmation of the final goal, deliverables, and acceptance criteria before implementation.
- Legacy projects without V1 adoption retain mandatory post-confirmation classification: deliverable projects must pass a four-lane, depth-2 Product Manager discovery gate before production roles are created or started. Pure synchronization/push, meeting-summary, filing/process, or read-only aggregation work may be exempt with a recorded reason and must be reclassified if scope expands.
- Lifecycle capability discovery for every registered Chief at six key events, while retaining the legacy startup-only profile shape for compatibility. Full lifecycle mode searches reusable local, official, open-source, managed, data/model, testing, operational, and expert surfaces, then produces at most one deduplicated material pack with three fixed-version candidates. It is discover/evaluate/recommend only: installation, pulls, downloads, enablement, account connections, dependencies, payment, outreach, external sends, production use, and project mutation remain separately authorized. Testing candidates go first to the Testing Director; visual direction stays with the Creative Director.
- Continuous phase dispatch until final acceptance, with a three-level management hierarchy by default.
- One accountable main task for user communication.
- Durable Chiefs named `Chief of <domain or project>｜<optional local-language label>`; the registered general office, TODO, and non-Chief context migration monitor are title exceptions, while other non-Chief durable roles use `Role｜Work outcome`.
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
- When explicitly enabled, autonomy policy groups foreseeable goal actions into one conditional approval package and reuses only currently revalidated approved items. Preparation, evidence collection, and candidate defects remain separate: preparation is only a pure rename/move, packaging-path correction, or material-evidence completion with retained semantic-invariance evidence; behaviour and security corrections remain exact candidate defects. A genuine new phase renews only its local defect allowance; prior permission, safety, denial, and consumed-budget boundaries remain unchanged. Final visual selection and final acceptance may stay deferred gates on their affected surfaces.
- Optional approved-decision relay gives TODO one transport-only action: it relays an already-approved nonvisual decision's stable ID and exact words once to its unique current source Chief, while General Office audits asynchronously. Delivery never equals execution, approval, or Testing; new requests still enter through General Office and visual decisions remain Creative-Director-only.
- Evidence-backed Creative Director scans at 11:00 and 20:00 Beijing time, with no more than one pending creative recommendation. When the visual gate is enabled, it also becomes the only operator-facing visual review hub: it receives project preview packets and relays only the operator's exact decision back to the source Chief.
- An independent cloud deployment registry; a registry record never authorizes production work.
- An optional human visual-selection gate: projects submit clickable previews only to the pinned `Chief of Creative Direction｜创意总监`; project Chiefs, roles, the general Chief task, and TODO must not duplicate the request, and no unselected option may become the final version.
- An optional pinned, cross-project unanswered-Chief TODO with configurable reminders; disabling it stops all reminder runs.

## Token 成本与适用对象 / Token cost and intended users

**中文**

Chief of Staff 是一个强调长期上下文、岗位分工、独立复核和持续跟进的编排层，因此可能让 Token 用量明显高于完成同一项工作的单代理对话。每个长期任务和 subagent 都会执行自己的模型推理与工具调用；并发岗位越多、上下文越长、复核轮次越多，增量通常越明显。OpenAI 官方文档同样说明，subagent 工作流会比可比的单代理运行消耗更多 Token。[OpenAI Subagents 文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)

- **企业或成熟团队：推荐直接使用。** 它更适合跨产品、研发、测试、合规和部署的长周期项目，尤其是需要职责隔离、审批记录、证据链和统一汇报的场景。建议同时设置并发上限、模型路由、阶段预算和停止条件。
- **个人用户或新手：建议按需启用。** 简单任务不要启动完整 Chief 层级；优先使用 `core` 预设、单阶段/单写入者和更低成本模型。编码、诊断、审查和证据化执行可显式调用本仓库原创的 `$kai-lean-execution`，在不缩小目标或跳过验收的前提下减少无效调查、重复计划和冗长日志；长对话迁移仍使用 `context-handoff`。该 Skill 不承诺固定比例的 Token 节省。
- **不要以“烧 Token”作为成果指标。** 应以完成交付物、验证证据、阻塞解除时间和最终验收为准。降 Token Skill 也不能代替人工审批、完整验收或原始记录留存。

(  ᴖ ̫ᴖ)

**English**

Chief of Staff is an orchestration layer built around durable context, role separation, independent review, and proactive follow-up. It can therefore use substantially more tokens than a comparable single-agent conversation. Every durable task and subagent performs its own model and tool work; additional parallel roles, longer contexts, and repeated review cycles generally increase that overhead. OpenAI's documentation likewise notes that subagent workflows consume more tokens than comparable single-agent runs. [OpenAI Subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents)

- **Enterprises and mature teams: recommended for direct use.** It fits long-running cross-functional work that benefits from ownership boundaries, approval records, evidence trails, and consolidated reporting. Configure concurrency limits, model routing, phase budgets, and stopping conditions.
- **Individuals and beginners: enable it selectively.** Do not start the full hierarchy for a simple task. Prefer the `core` preset, one phase/one writer, and lower-cost models. For coding, diagnosis, review, and evidence-backed execution, explicitly invoke this repository's original `$kai-lean-execution` to reduce redundant investigation, repeated planning, and log-heavy reporting without narrowing the goal or skipping acceptance. Use `context-handoff` for actual long-conversation migration. The Skill promises no fixed token-saving percentage.
- **Token burn is not a success metric.** Evaluate delivered artifacts, verification evidence, blocker resolution, and final acceptance. A token-reduction Skill must not replace human approvals, complete validation, or retention of auditable source records.

## 环境要求 / Requirements

**中文**

- 支持 Skills 和 subagents 的新版 Codex 桌面端、Codex CLI 或 IDE 扩展。
- 项目初始化器需要 Python 3.9 或更高版本。

( ⌯⥿⌯ )

**English**

- A current Codex desktop app, Codex CLI, or IDE extension with Skills and subagents enabled.
- Python 3.9 or newer for the project initializer.

## 安装 / Install

**中文**

使用上方[固定版本安装与同步流程](#chief-202-installation-and-explicit-fleet-sync)。将唯一、干净的 `v2.0.2` checkout 直接放在个人 Skills 目录，或将 Skill 入口链接到选定 checkout；不要复制出另一个独立演进的 Chief 真源。先核对并保留已有安装、链接和本地更改。可选 companion Skill 入口可链接到同一固定 checkout 内的对应目录。

原 Chief 明确重读并采用固定版本后继续当前任务；同步本身不要求新建任务或重启。主机尚未识别 Skill 时，按主机加载机制刷新；这与项目采用是两件事。

(ˊo̶̶̷ᴗo̶̶̷\`)

**English**

Use the [fixed-version installation and sync workflow above](#chief-202-installation-and-explicit-fleet-sync). Keep one clean `v2.0.2` checkout directly in the personal Skills directory, or point its Skill entry to that chosen checkout with a symlink. Do not create independently evolving Chief copies. Inspect and preserve any existing installation, link, and local changes first. Optional companion Skill entries can reference their corresponding directories in the same pinned checkout.

After explicitly rereading and adopting the pinned version, the existing Chief continues in its current task; sync does not require a new task or restart. If the host has not discovered a Skill, refresh it through the host's loading mechanism; that is separate from project adoption.

## 首次偏好配置 / First-use preference setup

**中文** <img src="assets/readme/anarrator/blueeyes.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

克隆固定版本和登记 Skill 入口本身不会运行任何脚本，也不会立刻弹窗。首次输入以下任一命令时才会开始配置：

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
- `project_start_capability_discovery.enabled`（兼容键：旧配置为启动/生产前复核；完整配置为所有 Chief 的关键节点能力发现，仅发现、评估与推荐）
- `visual_selection_gate.enabled`
- `american_english_coaching.enabled` 与 `include_casual_chat`
- `audio_playback.enabled`、`provider`、`clips`、`voice`、`rate` 与 `storage_root`
- `operator_salutation.enabled/value`
- `paused_title_prefix.enabled/value`
- `reminders.enabled`、时区、日间窗口、周期与额外提醒时间

配置器只更新 `AGENTS.md` 中带标记的受管片段，不覆盖其他规则。双语预设默认采用 `host_builtin`：Skill 仅提供书面、口语和地道用法文本，由 Codex/ChatGPT 客户端的内置语音或朗读控件负责播放，不生成音频文件，也不声称能自动播放某一句。仅当用户主动选择 `auto` 或 `macos_say` 离线附件模式时，才分别为启用的书面和口语文本生成内容寻址的 `.m4a`；外置存储、macOS `say` 或所选声音不可用时只返回文字，不写入其他目录。

^ Ⅰ    ̫   Ⅰ ^)⏝

**English**

Cloning the fixed release and registering its Skill entry never runs setup by itself. Setup begins only when you enter one of these prompts:

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

## 使用 / Use

**中文** <img src="assets/readme/anarrator/ribbons.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

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

兼容保留的 `.chief-of-staff/product-discovery.json` 在初始化时为 `pending/unclassified`，不会猜测项目类型。目标确认后的纯协调项目示例：

```json
{
  "classification_status": "classified",
  "project_classification": "coordination_only",
  "product_manager_required": false,
  "exemption_reason": "仅同步并推送已经批准的变更",
  "gate_status": "exempt"
}
```

未采用 V1 的交付型项目改用 `deliverable_project`，任命产品经理并完成四条证据线后，`gate_status` 才能变为 `passed`。

Skill 会读取 `primary_task_title` 并把当前主任务重命名为该值。所有长期 Chief 标题都必须以 `Chief of ` 开头；登记的全局总务、TODO 与非 Chief 上下文迁移监视器是标题例外，其他非 Chief 长期岗位继续使用 `职务｜工作内容`。普通 Chief 默认不置顶（`pin_primary_task=false`），未置顶不是故障。只有 general office、TODO、Creative Director 和 context migration monitor 四个中央角色强制置顶；Testing Director 是普通、默认不置顶的 coordination-only 证据角色，也不占 optional seat。可选产品 Chief 必须先由一般办公室形成最多 3 名、最多 1 个待决包，再由 TODO 只读核验身份、时效、重复、证据新鲜度、容量与 lineage，最后由妈妈逐项批准任命和置顶。默认最多 6 个可选席位，并保护人工 non-Chief pins；历史保留席位统一称为 grandmothered optional Chiefs，在价值复核前保持现状但不自动继承。容量满时只给 paired replacement recommendation，不自动挤出。置顶批准不等于目标确认，也不授权工程、设计或生产，适用的发现要求保持不变（V1 按当前工作，旧版按项目产品门）。仅 mandatory/approved lineage 可在安全核心交接候选后建立一个 replacement；自动化 parity 与 fresh `list_threads` 精确 ID 复核必须在最终 `MIGRATION_READY`、接管和归档 predecessor 前通过，`pinned:true` 回执不是证据。

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

✧ 𖦹

**English**

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

The retained compatibility state `.chief-of-staff/product-discovery.json` is initialized as `pending/unclassified`; the initializer never guesses the project type. A coordination-only example after goal confirmation is:

```json
{
  "classification_status": "classified",
  "project_classification": "coordination_only",
  "product_manager_required": false,
  "exemption_reason": "Only synchronize and push an already-approved change",
  "gate_status": "exempt"
}
```

A legacy deliverable project uses `deliverable_project`, appoints the Product Manager, and can reach `gate_status: passed` only after all four evidence lanes are complete.

The Skill reads `primary_task_title` and renames the current main task to that exact value. Every durable Chief title starts with `Chief of `; the registered general office, TODO, and non-Chief context migration monitor are title exceptions, while other non-Chief durable roles use `Role｜Work outcome`. Ordinary Chiefs default to unpinned (`pin_primary_task=false`), and that is not a defect. Only the general office, TODO, Creative Director, and context migration monitor are mandatory pins. The Testing Director is an ordinary, default-unpinned, coordination-only evidence role and occupies no optional seat. An optional product Chief requires a general-office pack of at most three candidates, read-only TODO checks of identity, currentness, duplication, evidence freshness, capacity, and lineage, then the operator's explicit appointment and pin approval. The default optional limit is six; manual non-Chief pins are protected. Historically retained slots are called grandmothered optional Chiefs; they remain unchanged pending value review but do not inherit automatically. Full capacity yields only a paired replacement recommendation. Pin approval does not confirm the goal or authorize engineering, design, or production; applicable discovery remains required (per work in V1; the project-wide gate in legacy projects). Only a mandatory or approved lineage may create one replacement after a safe core handoff candidate; automation parity and a fresh exact-ID `list_threads` check must pass before final `MIGRATION_READY`, takeover, and predecessor archival. A `pinned:true` receipt is not proof.

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

## 协作模型 / Coordination model

**中文** <img src="assets/readme/anarrator/cake.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

V1 优先由 Chief 直接执行；下图是需要委派时的可用结构，不是强制创建清单。

```text
用户
└── Chief of 个人web
    ├── 产品经理｜产品发现与立项（新产品完整发现及旧版交付型路由必需）
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

⋆｡˚〜

**English**

```text
User
└── Chief of Personal Web
    ├── Product Manager｜Discovery and charter (required for new-product full discovery and legacy deliverable routing)
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

## 项目空间与 Recents / Project space and Recents

**中文**

Chief 创建长期岗位前会读取自己的 Codex `projectId`，用同一个项目目标创建子岗位，并把该 ID 写入任务登记。这样岗位的上下文、工作区和状态都归属于正确项目。若 Chief 尚未处在已保存项目中，它会优先使用临时 subagents；只有确实需要独立长期历史时才请你先选择或保存项目。

Codex 会把长期任务视为可以独立恢复的任务，因此活动中的项目岗位仍可能出现在 Recents。这个入口的好处是集中显示运行、失败和等待处理的状态，避免必须逐个进入项目才能发现异常。当前版本采用折中生命周期：运行中、失败或待处理的岗位保持可见；普通最终汇报经 Chief 按 `exception_only` 审查、证据写入项目状态且无需返工后才归档，项目最终完成仍由操作者确认。归档可恢复，不会删除任务 ID、结果摘要或项目内登记。

ψ(´ڡ\`♡)

**English**

Before creating a durable role, the Chief resolves its Codex `projectId`, creates the child against the same project target, and records that ID in the task registry. If the Chief is not in a saved project, it defaults to temporary subagents and asks the user to select or save a project only when separate durable history is necessary.

Codex treats durable tasks as independently resumable tasks, so active project roles may still appear in Recents. That shared view is useful for surfacing running, failed, and needs-attention states without opening every project. This Skill therefore uses a lifecycle policy: active or actionable roles remain visible; under `exception_only`, the Chief archives a routine child only after reviewing its final handoff, recording evidence, and confirming that no retry remains. Final project completion still requires the operator. Archiving is reversible and preserves the task ID, result summary, and project registry record.

## 岗位对接与多 Agent 会议 / Peer coordination and multi-agent meetings

**中文** <img src="assets/readme/anarrator/rollcake.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

Chief 会在 `task-registry.json` 中为确有工作交集的同项目岗位建立双向 `coordination_with` 关系。登记后的岗位可以直接发送结构化对接消息，讨论依赖、接口、证据或交接；对接结论或未解决冲突必须回传 Chief。普通对接不需要你审批，也不会绕过 Chief 形成第二套项目计划。

每个长期岗位可以自行召开临时 subagent 会议，默认最多三名参与者。会议必须有一个明确问题、互不重叠的角色、输入证据、停止条件和综合负责人。参与者默认只读，不能继续创建长期岗位；如需实施，仍只有一个写入者。岗位负责人等待全部结果后按证据综合，再将简明结论发给相关岗位与 Chief。

ミ^・x・^)𓈒໒꒱

**English**

The Chief creates symmetric `coordination_with` edges in `task-registry.json` for same-project roles with a real dependency. Registered peers may directly exchange structured messages about interfaces, evidence, dependencies, or handoffs, then copy the outcome or unresolved conflict back to the Chief. Routine coordination needs no human approval and cannot create a competing project plan.

Every durable role may convene a temporary subagent meeting with up to three participants by default. A meeting has one question, non-overlapping roles, evidence inputs, a stopping condition, and a synthesis owner. Participants are read-only by default and cannot create durable roles; if implementation is included, exactly one participant owns the write surface. The parent waits for all results, reconciles them by evidence, and sends one concise outcome to affected peers and the Chief.

## 待回复 TODO 与提醒（可选） / Unanswered-Chief TODO and reminders (optional)

**中文** <img src="assets/readme/anarrator/pinkdoll.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

提醒是个人级、跨项目服务，不会让每个 Chief 重复创建一套自动化。只有统一偏好中的 `reminders.enabled` 为 `true` 时，Skill 才创建或复用一个置顶的 `TODO｜待回复 Chief 汇总` 对话；它只收集 Chief 明确等待你审批、确认、决策、补充信息或权限选择、且尚无后续用户回复的事项。视觉选择只认 `Chief of Creative Direction｜创意总监` 为权威来源：项目 Chief、岗位、“一人之下”和旧审阅中心中的副本全部排除，并把创意总监持有的多个视觉 ID 合并为一个待回复入口。仅仅打开或阅读对话不会被误判为已回复。

(   ˊᵕˋ  )

**English**

Reminders are one personal, cross-project service rather than one automation per Chief. Only when `reminders.enabled` is `true` does the Skill create or reuse a pinned `TODO｜待回复 Chief 汇总` thread. It includes only Chiefs that explicitly await approval, confirmation, a decision, more information, or a permission choice and have no later resolving user reply. For visual selections, only `Chief of Creative Direction｜创意总监` is authoritative; copies in project Chiefs, roles, the general Chief task, and retired hubs are excluded, and multiple visual IDs are grouped under that one task. Merely opening or reading a thread does not clear an item.

## 视觉决策只进创意总监 / Visual decisions go only to the Creative Director

**中文** <img src="assets/readme/anarrator/bluedoll.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

启用 `visual_selection_gate` 后，项目 Chief 负责制作或组织可点击的 NON-FINAL 预览，但只能把稳定决策 ID、差异、证据和影响提交给唯一置顶的 `Chief of Creative Direction｜创意总监`。创意总监可以同时持有多个视觉待决项，并将新变化合并成一条简洁审阅消息；“最多一条待定建议”的限制只约束主动创意建议，不限制项目送来的视觉审批。

创意总监不能替操作者选择、实施设计、安装构建或修改来源项目。收到操作者明确决定后，它只把原话、决策 ID 和边界回传来源 Chief。若操作者没有及时回复，创意总监保持等待，不重复催促；后续由统一 TODO 扫描创意总监，而不是让每个项目再次提醒。

示例预设采用北京时间 09:00–18:00 每小时一次（包含 09:00 和 18:00），并在 22:00 再提醒一次；时区、日间窗口、间隔和额外时间都可调整。保存偏好不会自行创建自动化，仍需 Skill 通过 Codex 的定时任务接口建立或更新。关闭时会暂停该策略登记的全部自动化，因此不会运行扫描，也不会发送通知；保留 TODO 对话和 ID 便于以后恢复。

🩵o .o)🩷🩵(o。o🩷

**English**

With `visual_selection_gate` enabled, a project Chief creates or organizes clickable NON-FINAL previews, then submits the stable decision ID, differences, evidence, and impact only to the single pinned `Chief of Creative Direction｜创意总监`. The Creative Director may hold multiple incoming visual decisions and batches newly changed items into one concise review message. The one-pending-recommendation limit applies only to proactive creative suggestions, not to project-submitted visual approvals.

The Creative Director cannot choose for the operator, implement the design, install a build, or modify the source project. After an explicit operator decision, it relays only the exact wording, decision ID, and boundary to the source Chief. If the operator has not replied, the Creative Director waits without repeated nudges; the shared TODO later discovers that one task instead of every project reminding separately.

The example preset uses every Beijing-time hour from 09:00 through 18:00 inclusive, plus 22:00; timezone, daytime window, interval, and additional times are configurable. Saving a preference does not create an automation by itself: the Skill still uses Codex's scheduled-task interface to create or update it. Disabling pauses every automation recorded by the policy, producing no scan runs or notifications while preserving the TODO thread and identifiers for later re-enablement.

## 汇报批复机制 / Report approval workflow

**中文**

默认 `report_review_mode` 为 `exception_only`。子岗位仍须提交唯一汇报编号、证据、风险和下一步，但普通进度与岗位最终交接由项目 Chief 按执行契约审查，不再直接请求操作者批准。Chief 会检查范围、唯一写入面、验收证据、测试、冲突和高影响边界，并把审查依据写入 `approval-queue.json`。

只有目标确认、实质产品选择、视觉选择、高影响操作、安全问题、范围或写入权冲突、失败/证据不足、扩层和项目最终交付才升级给操作者。例外请求使用 `USER_ACTION_REQUIRED`；普通岗位交接使用 `CHIEF_REVIEW_READY`，由 Chief 批准、退回或继续派发。项目最终完成仍必须由操作者确认。

兼容模式 `all_reports` 可恢复每份里程碑/最终交接都由操作者批准的旧行为；此时 `report_approval_required` 为 `true`。无论采用哪种模式，汇报批准都不会自动授权删除、发布、生产变更、支付、外发消息或扩大权限。

꒰ঌ(っ˘꒳˘ｃ)‪໒꒱

**English**

The default `report_review_mode` is `exception_only`. Roles still return a unique report ID, evidence, risks, and next steps, but the project Chief reviews routine progress and role-final handoffs against the execution contract instead of asking the operator. The Chief checks scope, exclusive write ownership, acceptance evidence, tests, conflicts, and protected-action boundaries, then records its decision basis in `approval-queue.json`.

Only goal confirmation, material product choices, visual choices, protected actions, safety issues, scope or ownership conflicts, failed or unverifiable work, depth expansion, and final project completion reach the operator. Exceptions use `USER_ACTION_REQUIRED`; routine role handoffs use `CHIEF_REVIEW_READY`, and the Chief approves, requests changes, or advances the work. Final project completion still requires the operator.

Compatibility mode `all_reports` restores the previous behavior in which every milestone/final handoff requires operator review and sets `report_approval_required` to `true`. In either mode, report approval never authorizes deletion, release, production changes, payments, external messages, or permission expansion.

## 主席负责制 / Chair-led cabinet governance

**中文**

启用 `governance_model.mode = chair_led_cabinet` 后，操作者只保留最终目标、重大产品路线、视觉选择、高影响操作、Chief 任免/暂停及项目最终验收等权力。项目 Chief 对日常行政、岗位管理、普通验收、一次限界返修和安全范围内的阶段推进负全责；只读复核者只有证据核验权。

普通岗位使用 `CHIEF_REVIEW_READY` 向项目 Chief 汇报。非视觉法定例外使用 `CHAIR_BRIEF_READY` 交给“一人之下”，由它压缩、去重后才能向操作者发出 `USER_ACTION_REQUIRED`；视觉决定仍只进入创意总监。TODO 只扫描这两个权威入口。等待决定只冻结受影响的写入面，其他安全路线必须继续。

可选启用 `governance_model.continuation_policy` 后，项目 Chief 必须选择证据最强、在范围内且安全的继续路径并直接执行。只要这种路径仍存在，就不把停止、保留失败状态或延期列成需要操作者选择的并列方案；普通失败继续由 Chief 通过限界诊断、修复和复检负责。只有继续本身需要新增权限或创建新 Chief 时才报备。该规则不会授权高影响操作、绕过视觉门、隐藏安全证据、改变写入权或扩张已确认目标。

(   ᵒ̴̶̷̤-ᵒ̴̶̷̤ )

**English**

With `governance_model.mode = chair_led_cabinet`, the operator retains final-goal, material product-direction, visual-selection, protected-action, Chief appointment/pause/removal, and final project acceptance powers. Project Chiefs are accountable for routine administration, role management, ordinary acceptance, up to three focused repair-and-independent-recheck cycles after the initial independent verification, and safe phase advancement. Read-only verifiers have evidence authority only.

Routine roles use `CHIEF_REVIEW_READY`. Non-visual statutory exceptions use `CHAIR_BRIEF_READY` to the general office, which deduplicates and compresses them before emitting `USER_ACTION_REQUIRED`; visual decisions remain exclusive to the Creative Director. TODO scans only those two authoritative hubs. Waiting freezes only the affected write surface while independent safe work continues.

When `governance_model.continuation_policy` is enabled, each project Chief executes the strongest evidence-backed safe in-scope continuation. Stopping, preserving a failed state, and delaying are not peer options while such a path exists. Only a continuation that itself needs a new permission or a new Chief is escalated. Protected actions, visual gates, safety disclosure, write ownership, and the confirmed goal remain unchanged boundaries.

## 旧版产品分类与产品发现门（未采用 V1） / Legacy product classification and discovery gate (without V1 adoption)

**中文**

初始使命、目标边界和验收确认后，Chief 必须先写入 `.chief-of-staff/product-discovery.json`。创建或实质改变产品、服务、代码、设计、内容资产或其他需验收交付物的项目属于 `deliverable_project`；仅同步或推送既定变更、会议总结、备案/流程推进、只读审计或汇总可列为 `coordination_only`，但必须记录具体豁免理由。协调型项目一旦扩展到产品创作或实质交付，豁免立即失效并重新分类。

交付型项目必须任命一个 depth-2 产品经理阶段负责人。产品经理不是 Chief，也不形成第二控制面；其四条必备证据线是项目立项、需求分析、市场调研和非绑定的架构可行性。临时 helper 固定为 depth 3，不能继续委派或创建长期岗位；运行时没有 subagent 时，产品经理可在单任务中分别完成四条证据线，但必须记录运行限制，不能省略产出。综合结论覆盖目标/非目标/指标、市场与竞品、用户与痛点、政策和商业可行性、需求分层与剔除依据、用户画像、技术约束、风险/证据缺口、推荐 MVP 和可追溯证据索引。

产品门通过前，只能进行目标澄清、只读发现、需求研究和可逆规划；创建或启动工程、设计、内容生产等岗位前必须运行初始化器的 `--check`，非零结果就是硬阻断。不得伪造访谈、问卷或市场数据；真人外联、问卷发送、付费数据、受限访问和其他高影响操作仍需独立授权。架构线只提供可行性、接口、约束和风险，不替代后续技术负责人的最终架构权；体验目标可记录，但可点击 NON-FINAL 视觉选项仍只送创意总监。旧项目缺字段时迁移为 `legacy_unclassified/legacy_pending`，不会伪造已通过，并必须在下一次新增生产阶段前完成分类和必要产品门。

꒰ ՞ɞ̴̶̷̥⩊ɞ̴̶̷̥꒱֯

**English**

After the initial mission, goal boundary, and acceptance contract are confirmed, the Chief records classification in `.chief-of-staff/product-discovery.json`. A project that creates or materially changes a product, service, code, design, content asset, or another acceptance-tested deliverable is a `deliverable_project`. Synchronizing or pushing an already-decided change, summarizing a meeting, advancing a filing/process, or performing read-only audit/aggregation may be `coordination_only`, but requires a concrete exemption reason. Any expansion into product creation or material delivery invalidates the exemption and triggers reclassification.

A deliverable project appoints one depth-2 Product Manager phase lead. The Product Manager is not a Chief and does not create a second control plane. Its four required evidence lanes are project initiation, requirements analysis, market research, and non-binding architecture feasibility. Temporary helpers are depth 3 and cannot delegate again or create durable roles. If subagents are unavailable, the Product Manager may complete all four lanes in one task only with a recorded runtime limitation and separate evidence for every lane. The synthesis covers the charter, goals/non-goals/metrics, market and competitors, users and pain points, policy and business feasibility, prioritized and rejected requirements, personas, technical constraints, risks and evidence gaps, a recommended MVP, and a traceable evidence index.

Before the gate passes, only goal clarification, read-only discovery, requirements research, and reversible planning are allowed. The initializer's `--check` is a required fail-closed preflight before creating or starting engineering, design, content-production, or other production roles. Interviews, surveys, and market facts must never be invented; outreach, survey delivery, paid data, restricted access, and every protected action retain separate approval gates. Architecture discovery is advisory and cannot bind the later Technical Lead. Experience goals may be recorded, but clickable NON-FINAL visual options remain exclusive to the Creative Director. Existing projects missing these fields migrate to `legacy_unclassified/legacy_pending`, never to a fabricated pass, and must classify before adding the next production phase.

## 目标闭环与主动推进 / Goal closure and proactive progression

**中文** <img src="assets/readme/anarrator/sundae.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

初始化后，Chief 会先根据项目上下文提出最终目标、交付物、验收标准、非目标和约束，请你确认或修改。新项目在你明确确认前只允许为澄清目标进行有限的只读侦察。旧项目迁移时允许已经开始的非高影响任务完成，但不会派发新任务或进入新阶段。确认结果和逐项验收证据保存在 `project-plan.json`。

目标确认后，Chief 将工作拆为阶段，并确保未完成项目始终满足以下之一：V1 有当前工作记录（Chief 可直接执行），旧版有岗位正在排队、工作或等待处理；正在等待你的具体决定；或者存在有证据且有解除条件的阻塞。如果本阶段岗位全部结束但最终验收仍未满足，Chief 会直接执行或在有收益时委派，推进下一个符合准入条件的工作，而不是只回答“当前无待审批事项”。

需要委派时，可用层级为 `Chief → 阶段负责人 → 执行岗位/临时 subagents`。阶段负责人可以在授权范围内创建执行岗位；临时 subagents 不能继续创建长期岗位。需要第四层时，Chief 必须先说明原因、期限、岗位结构和不扩层的影响并向你申请。

未完成项目的 Chief 汇报固定包含最终目标、当前阶段、已验证进展、正在工作的岗位、距最终交付的差距和下一检查点。只有全部最终验收标准都有证据时才能宣布项目完成。

(  ᓀ⩊<)

**English**

After initialization, the Chief drafts the final goal, deliverables, acceptance criteria, non-goals, and constraints from available project context and asks you to confirm or revise them. A new project permits only bounded read-only discovery before explicit confirmation. During migration, already-running non-high-impact tasks may finish, but no new task or phase starts. The confirmed contract and criterion-level evidence live in `project-plan.json`.

Once confirmed, the Chief divides the work into phases. Until final acceptance, V1 must have a current work item (which the Chief may execute directly), and legacy projects must have an active, queued, or attention-needed role; be waiting for an exact user decision; or be blocked with evidence and a release condition. If every role in a phase stops while final acceptance remains unmet, the Chief advances the next admitted safe in-scope work, directly or by justified delegation, instead of replying only that no approval is pending.

When delegation is justified, the available hierarchy is `Chief → Phase Lead → Execution Role/temporary subagents`. Authorized phase leads may create execution roles; temporary subagents cannot create durable roles. A fourth management level requires the Chief to request approval with the reason, duration, proposed structure, and impact of refusal.

Every unfinished-project report includes the final goal, current phase, verified progress, active roles, remaining delivery gap, and next checkpoint. The Chief may declare completion only when every final acceptance criterion has supporting evidence.

## 有效吞吐、创意与部署 / Effective throughput, creativity, and deployments

**中文** <img src="assets/readme/anarrator/kittens.gif" width="20" height="20" alt="啊旁白像素动图" title="啊旁白 / ANARRATOR">

`effective_throughput` 以已完成且有证据的验收为中心。默认至多两个无共享写入面的独立阶段并行；每个检查点必须关联具体验收证据，连续两个检查点无证据时，Chief 停止该线路并自查目标、范围、依赖、写入权、验收方法和阻塞原因。

只有最终目标已确认、验收可验证且没有待处理人工门时才可使用 `/goal`。创意总监在北京时间每天 11:00 和 20:00 执行有证据的主动扫描，最多保留一条待定创意建议；同时可作为唯一视觉审阅中心接收项目预览并回传妈妈原话。除登记过的视觉决定回传外，它只读其他项目、不主动干预、不改文件。偏好证据分为明确偏好、一致模式和单次假设；新项目建议至少需要两个不同项目的明确偏好或一致模式证据，并包含目标用户、最小验证、成功阈值和停止条件。

当云部署工作被明确纳入范围时，应在独立 registry 中登记目标与证据；该记录是库存与审计记录而非执行凭证。生产部署、生产变更、发布或回滚均须在操作前单独取得明确用户批准。

(  ᴖ ̫ᴖ)

**English**

`effective_throughput` centers on completed acceptance backed by evidence. By default, at most two independent phases with no shared write surface run concurrently. Every checkpoint needs concrete acceptance evidence; after two checkpoints without evidence, the Chief stops that lane and reviews its goal, scope, dependencies, ownership, acceptance method, and blocker.

Use `/goal` only with a confirmed, verifiable final goal and no pending human gate. The Creative Director runs evidence-backed scans at 11:00 and 20:00 Beijing time and retains at most one pending proactive suggestion. It may also receive visual previews as the sole review hub and relay the operator's exact decisions. Outside registered visual-decision relays, it remains read-only across other projects. Preference evidence distinguishes explicit preferences, consistent patterns, and single hypotheses. A new-project suggestion needs explicit or consistent-pattern evidence from at least two projects, with target users, a minimal validation, success criteria, and stop conditions.

When cloud deployment is explicitly in scope, register targets and evidence separately. This is an inventory and audit record, not execution authority. Production deployment, changes, release, and rollback each require separate explicit approval immediately before the action.

## 全局上下文无损接续 / Global loss-aware context rollover

**中文**

仓库同时提供 `context-handoff` Skill。它只使用最新输入 token 与模型上下文窗口的比值：75%刷新检查点，85%在安全边界创建 `原对话名｜续N`，95%进入紧急迁移。累计 token 和账户限额不会被误当成上下文占用。

检查点捕获只把“捕获后 source session 改变”和无覆盖意图的迁移编号碰撞视为瞬时竞态。每个 source-task 安全边界最多执行一次原子 build+verify，始终使用下一个未占用的单调编号，绝不覆盖或删除旧包；后续安全边界自动继续，不再询问妈妈是否重试。连续三次瞬时失败转为 Chief 自管的只读诊断与退避。之所以禁止紧循环，是因为反复捕获会持续占用磁盘与 I/O、改写自身 session 并掩盖权限、存储、工作树、校验或 parity 缺陷。低于 75%取消陈旧触发；有效 bundle 产生前不得创建 successor。

项目迁移包保存在 `.codex/context-migrations/`，无项目任务保存在 `~/.codex/context-migrations/`。新对话必须返回 `MIGRATION_READY` 并核对目标、审批、任务关系、写入权、Git 状态、证据、下一步、暂停状态和全局规则。若原任务绑定自动化，迁移包还必须逐项记录精确 ID、名称、类型、目标 task ID、状态、schedule、prompt SHA-256 和通知策略；在接管、切换权威入口或归档 predecessor 前，复用并重绑到精确 successor task ID，再用 live automation view 核验。配置引用和 update receipt 不是证明。缺失时仅在既有授权内建立一个最小等价项；禁止同职责 ACTIVE 重复，且必须保持 schedule、prompt 语义、通知策略和范围。任一不一致均记录 `automation_rebind_failed`、返回 `MIGRATION_BLOCKED` 并保持 predecessor active/unarchived。

普通未获批 Chief 的 successor 不继承置顶，也不因未置顶触发替换。只有 mandatory 或妈妈批准的 optional lineage，在完成 bundle parity、automation parity 与适用的 pin parity 后，才可接管；置顶 successor 仍须用 fresh `list_threads` 独立确认精确 task ID 位于 `pinnedThreads`，`pinned: true` 只表示操作已受理。失败则记录 `pin_verification_failed`，不接受接管，并按安全边界的同项目单 replacement 流程处理。旧对话不会删除，不得重复 Chief、改变范围、恢复暂停或绕过审批；已归档 predecessor 的历史自动化异常只修复 successor 绑定，不反向解档、删除或重复创建。

( ⌯⥿⌯ )

**English**

The repository also includes `context-handoff`. It uses only newest input tokens divided by the model context window: checkpoint at 75%, create `Original title｜Continuation N` at a safe boundary at 85%, and prioritize migration at 95%. Cumulative and account usage are ignored.

Checkpoint capture automatically tolerates only an exact source-session-change race or a non-overwriting migration-number collision. It performs at most one atomic build+verify per source-task safe boundary, always selects a new monotonic number, and never overwrites or deletes an older bundle. A later safe boundary retries without asking the operator; three consecutive transient failures enter Chief-owned read-only diagnosis/backoff. This is deliberately not a tight loop because repeated capture consumes disk/I/O, can mutate its own source session, and can hide permission, storage, worktree, validation, or parity defects. Below 75% the stale checkpoint trigger is cancelled; no successor is created before a valid bundle.

Project bundles live in `.codex/context-migrations/`; projectless bundles live in `~/.codex/context-migrations/`. A successor must return `MIGRATION_READY` and match goals, approvals, task graph, write ownership, Git state, evidence, next action, pause state, and global instructions. For each task-bound automation, the bundle records exact ID, name, kind, target task ID, status, schedule, prompt SHA-256, and notification policy. Before takeover, authority switching, or predecessor archival, reuse and rebind it to the exact successor task ID, then verify it in a fresh live automation view. Configuration references and update receipts are not proof. Only proven live absence plus existing authorization permits one minimal equivalent; duplicate ACTIVE same-duty automations are forbidden, and schedule, prompt semantics, notification policy, and scope remain unchanged. Any mismatch records `automation_rebind_failed`, returns `MIGRATION_BLOCKED`, and keeps the predecessor active and unarchived.

An ordinary unapproved Chief does not inherit a pin and never enters replacement merely because it is unpinned. For a mandatory or operator-approved optional lineage, bundle parity, automation parity, and applicable pin parity must all pass. A fresh `list_threads` exact-ID check remains mandatory; `pinned: true` is only an operation receipt. A failed check records `pin_verification_failed` and denies takeover. Predecessors remain recoverable; migration cannot create duplicate Chiefs, change scope or pause state, or bypass approval. Historical automation repair after archival never unarchives/deletes the predecessor or duplicates the task or automation.

## 当前限制 / Current limits

**中文**

- 第一版不修改 Codex 客户端界面；只在宿主已提供阻塞式选择面板时调用它，否则使用对话或 CLI 配置。
- 关闭 Codex 可能会停止正在运行的任务；持久状态保存在项目文件和 Codex 任务历史中。
- 当前不安装 AWS CLI Agent Orchestrator 等外置控制台；`control-plane.json` 仅预留未来适配入口。

(ˊo̶̶̷ᴗo̶̶̷\`)

**English**

- Version 1 does not modify the Codex client UI. It uses a native blocking selection panel only when the host already provides one, with conversational and CLI fallbacks.
- Closing Codex may stop active work; persistent coordination state is stored in project files and Codex task history.
- An external control plane such as AWS CLI Agent Orchestrator is not installed. `control-plane.json` reserves a future integration point.

## 仓库内容 / Repository contents

- `SKILL.md`：Skill 路由与操作说明。

  Skill routing and operating instructions
- `scripts/init_project.py`：安全的项目初始化与校验脚本。

  safe project initializer and validator
- `scripts/continuous_execution.py`：精确本地执行包校验与回流意图。

  exact local execution-package validation and return intents
- `scripts/configure_preferences.py`：幂等偏好配置器。

  idempotent preference onboarding
- `scripts/render_english_audio.py`：`auto`、`macos_say` 的可选离线附件渲染器，`host_builtin` 不调用。

  opt-in offline attachment renderer for `auto`/`macos_say`; never used by `host_builtin`
- `assets/project-template/`：项目契约与角色配置模板。

  generated project contract and agent profiles
- `assets/operator-preferences.example.json`：隐私安全的核心默认偏好。

  privacy-safe core defaults
- `assets/presets/`：可主动启用的偏好预设。

  opt-in preference presets
- `references/`：协调协议、项目路径可移植规则、可执行产品发现治理与持久状态结构。

  coordination protocol, project-path portability, enforceable product-discovery governance, and persistent state schema
- `references/continuous-execution.md`：连续执行的进展、回流、资源和委托测试边界。

  opt-in progress, return, resource, and delegated-testing boundary
- `references/operator-preferences.md`：首次配置、结构与隐私行为。

  onboarding, schema, and privacy behavior
- `assets/reminder-policy.example.json`：可选的个人提醒策略示例。

  optional personal reminder policy example
- `agents/openai.yaml`：Codex 界面元数据与自动调用策略。

  Codex UI metadata and implicit invocation policy
- `context-handoff/`：全局上下文检查点与校验接续 Skill。

  global context checkpoint and verified rollover Skill
- `kai-lean-execution/`：原创、仅显式调用的精简执行 Skill。

  original explicit-only lean execution Skill

## README 写入规则 / README writing rules

**中文**

- 每个模块内先中文、后英文，内容含义对应；不采用整篇中文后再整篇英文的排列。
- 颜文字只从妈妈提供的表达中选用，不再自行补充；仅用于中文正文，适量点缀；英文正文、标题、代码、命令及配置示例不添加颜文字。^ Ⅰ    ̫   Ⅰ ^)⏝
- 标题图使用已获确认的像素插画，保存在仓库内并使用相对路径引用；替换图片须先确认，不覆盖来源参考图。
- 修改排版与语气时保留技术事实、链接、命令和权限边界，不将文档美化变为制度变更。
- 图集内 10 个 GIF 全部使用，保留动画原文件；通过 HTML 图片尺寸设为 20×20 像素，仅在中文段落旁作小图标，不放大铺图。第三方动图来自用户提供的啊旁白 / ANARRATOR 图集，转载许可尚未核实，不属于本仓库代码许可证的授权范围；公开发布前须确认许可。
- 本规则模块始终位于 README 最底部；后续新增内容放在它之前。

**English**

- Pair Chinese and English within each module, with Chinese first and equivalent meaning. Do not split the document into two language-wide sections.
- Select kaomoji only from the operator-provided set; do not invent additions. Use them sparingly in Chinese prose only. Keep them out of English prose, headings, code, commands, and configuration examples.
- Use the approved pixel-art header, stored in the repository and referenced by a relative path. Confirm replacements first and preserve source references.
- Preserve technical facts, links, commands, and permission boundaries when changing layout or tone. Visual editing does not change operating policy.
- Include all 10 supplied GIFs as 20×20 HTML image icons beside Chinese prose, retaining the original animation files. These third-party assets are credited to 啊旁白 / ANARRATOR; redistribution permission has not been verified and is not granted by the repository's code license. Confirm permission before public distribution.
- Keep this writing-rules module at the very bottom of the README; insert future content above it.

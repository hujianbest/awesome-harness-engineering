# `packs/coding/` — HarnessFlow 工程工作流 Pack

`packs/coding/` 是 Garage 自带的 **HarnessFlow（HF）工程工作流 family pack**，把 product discovery → hypothesis experiment → spec → design → tasks → TDD 实现 → 多维 review → gate → finalize 的完整工程链路打包成 **29** 个可分发的 skill（28 个 `hf-*` + `using-hf-workflow`）。

下游用户在自己项目里 `garage init --hosts <list>` 之后，就能在挂载的宿主（Claude Code / OpenCode / Cursor）里加载 hf-specify / hf-design / hf-tasks 等 skill，按 SDD + 闸 TDD 流程驱动 AI Agent 做严肃工程任务。

## Pack 概况

| 字段 | 值 |
|---|---|
| `pack_id` | `coding` |
| `version` | `0.5.0` |
| `schema_version` | `1` |
| `skills` | 29（28 hf-* + 1 using-hf-workflow） |
| `agents` | 0 |
| 共享资产布局 | per-skill self-contained（每个 skill 自带 `references/`，无 family-level 共享目录） |

## 29 个 Skill 清单

### Public Entry（1）

| Skill | 用途 |
|---|---|
| `using-hf-workflow` | HF workflow family public entry：判断 entry vs runtime recovery，分流到 router 或 direct invoke |

### Authoring（5）

| Skill | 用途 |
|---|---|
| `hf-product-discovery` | 产品发现 / thesis / wedge / probe；尚未收敛到 formal spec 时使用 |
| `hf-experiment` | 假设验证 probe（Phase 0）：discovery / spec 阶段存在 blocking 或 low-confidence 假设时，跑一次最小可验证 probe 再决定是否推进主链 |
| `hf-specify` | 起草需求规格（EARS + BDD + MoSCoW + ISO 25010 QAS + Success Metrics） |
| `hf-design` | 起草实现设计（ADR + C4 + ARC42 + DDD + Event Storming + STRIDE + 失败模式） |
| `hf-ui-design` | 起草 UI 设计（IA + wireframe + Atomic + 状态矩阵）；规格含 UI surface 时与 hf-design 并行激活 |
| `hf-tasks` | 把已批准设计拆解为可评审任务计划（WBS + INVEST + 依赖图 + DoD） |

### Review（8）

| Skill | 用途 |
|---|---|
| `hf-discovery-review` | 评审 product discovery 草稿 |
| `hf-spec-review` | 评审需求规格（Q/A/C/G 四组 rubric） |
| `hf-design-review` | 评审实现设计（ATAM + Fagan + traceability） |
| `hf-ui-review` | 评审 UI 设计（peer with hf-design-review） |
| `hf-tasks-review` | 评审任务计划（粒度 + 追溯 + 依赖正确性） |
| `hf-test-review` | 评审实现完成后的测试质量 |
| `hf-code-review` | 评审实现代码质量（含 Clean Architecture conformance） |
| `hf-traceability-review` | 评审 spec → design → tasks → 实现 → 验证的追溯完整性 |

### Gate（3）

| Skill | 用途 |
|---|---|
| `hf-regression-gate` | 回归验证 gate（traceability review 通过后） |
| `hf-doc-freshness-gate` | 对外可见文档同步 gate（regression gate 之后、completion gate 之前；判定 user-visible behavior change 是否在 README / 公共 API doc / OpenAPI / docstring / i18n / CONTRIBUTING / 用户文档站等已同步刷新） |
| `hf-completion-gate` | 完成判定 gate（regression + doc-freshness gate 通过后） |

### Implementation & Branch（4）

| Skill | 用途 |
|---|---|
| `hf-test-driven-dev` | 单 active task 实现入口（TDD：fail-first → minimum implementation → verify green，含 Two Hats / Clean Architecture conformance） |
| `hf-hotfix` | 线上紧急缺陷修复支线 |
| `hf-increment` | 范围 / 验收 / 约束变更支线 |
| `hf-finalize` | Cycle closeout：状态收尾 + release notes + handoff pack |

### Verify-stage & release-tier（2）

| Skill | 用途 |
|---|---|
| `hf-browser-testing` | verify 阶段条件侧节点：DOM / Console / Network 三层运行时证据（观察不裁决；主链 FSM 不变） |
| `hf-release` | release-tier 独立 skill：多 feature closeout 后切 vX.Y.Z 版本（不进 router 主链 transition map） |

### Cross-task knowledge & author-side discipline（4）

| Skill | 用途 |
|---|---|
| `hf-wisdom-notebook` | 跨 task 知识累积（5-file schema + stdlib validator；与 `hf-completion-gate` §6.2 衔接） |
| `hf-gap-analyzer` | 作者侧自检（pre-Fagan；6 维 rubric；产出 gap-notes，由作者吸收后再送 review） |
| `hf-context-mesh` | 分层 `AGENTS.md` / Cursor rules / `CLAUDE.md` 脚手架生成（架构师选客户端；不代写约定） |
| `hf-ultrawork` | 显式 opt-in fast lane（6 条 escape；不绕过 Fagan / 三 gate） |

### Routing（1）

| Skill | 用途 |
|---|---|
| `hf-workflow-router` | Runtime 编排权威：profile / mode / isolation / canonical 节点 / review dispatch / 恢复编排（含 Garage 第一方 step 3.5 "F014 Workflow Recall"） |

## Per-Skill Self-Contained 布局

从 v0.4.0 起，本 pack 跟随上游 `harness-flow` 走 **per-skill self-contained** 路径：每个 skill 自己的 `references/` 子目录持有该 skill 用到的所有模板和共享文档。原 v0.3.0 在 `packs/coding/skills/{docs,templates}/` 与 `packs/coding/principles/` 下的家族级共享资产已经分发到各 skill 内（review-record-template / verification-record-template 等会在多个 skill 的 `references/` 下出现各自副本）。

下游影响：F007 安装管道**仅复制 `<pack>/skills/<id>/SKILL.md` 单文件**，不递归 `references/`。skill 内对 `references/<file>.md` 的引用属于**文档级提示**（指向用户本地 git checkout 的对应路径），不是装后宿主目录下的本地副本。

详见：

- spec § FR-804 验收（packs 源端 + 下游宿主端两层口径）
- design ADR-D8-4（文档级提示策略）
- design ADR-D8-9（NFR-801 文件级豁免清单）
- spec § 5 deferred backlog "D7 管道扩展为递归 references/" → D9 候选

## Garage 第一方增量 (vs upstream)

本 pack 与上游 `harness-flow` **默认内容一致**；Garage 侧唯一常驻差异仍是 `hf-workflow-router`：

- `SKILL.md` 在 step 3 与 step 4 之间额外插入 **step 3.5 "查历史路径 (F014 Workflow Recall)"**（advisory only）
- `references/recall-integration.md`：F014 advisory 块格式 / JSON schema / 何时省略 / 与 authoritative routing 的关系详解

由 `tests/adapter/installer/test_dogfood_invariance_F009.py` sentinel 守门 SHA 字节级一致；INV-F14-5 守门既有 step 1-10 + dogfood SHA baseline 不变。

详见 `docs/features/F014-workflow-recall.md` 与 `docs/designs/2026-04-26-workflow-recall-design.md`。

## 安装样板

下游用户在自己项目执行：

```bash
cd ~/projects/my-app
garage init --hosts claude
# stdout: Installed N skills, M agents into hosts: claude   (N == sum(三 pack.json.skills[]))
ls .claude/skills/ | grep -c '^hf-'   # → 28
ls .claude/skills/using-hf-workflow   # 存在
cat .claude/skills/hf-specify/SKILL.md | head -5
# → 含 installed_by: garage, installed_pack: coding
```

## 与 Garage 仓库自身的关系

本仓库自身贡献者首次 clone 后，需要先跑一次 dogfood 才能在 IDE 内加载这 29 个 skill：

```bash
cd /path/to/garage-agent
garage init --hosts cursor,claude
# → 在仓库根 dogfood 出 .cursor/skills/ + .claude/skills/，IDE 即可加载
# 注：.cursor/skills/ 与 .claude/skills/ 在 .gitignore 内排除，不入 git 追踪
```

详见 `AGENTS.md § "本仓库自身 IDE 加载入口"` 段。

## 上游 (Reverse-sync 来源)

本 pack 内容 reverse-sync 自 [`hujianbest/harness-flow`](https://github.com/hujianbest/harness-flow) upstream。

### v0.5.0 同步 — 跟随 harness-flow main（对齐上游 v0.6.0 pre-release 能力集，2026-05）

- 全量覆盖 `skills/*` 自 [`hujianbest/harness-flow`](https://github.com/hujianbest/harness-flow) **main** shallow clone（与上游 v0.6.0 README scope note 对齐：router step-level recovery、`hf-browser-testing` / `hf-context-mesh` / `hf-gap-analyzer` / `hf-release` / `hf-ultrawork` / `hf-wisdom-notebook` 等）
- 上游已移除 `hf-bug-patterns`（PR #31）；本 pack `packs/coding/pack.json` 同步删除该 skill id
- **NFR-801 守门**：`hf-context-mesh` 与 `hf-finalize` 中不可避免的宿主路径字面量已用 ZWSP 断字以通过 `test_neutrality_exemption_list.py` strict 层（不改变人类阅读语义）
- 第一方保留：`hf-workflow-router/SKILL.md` step 3.5 + `references/recall-integration.md`（F014 增量）

### v0.4.0 同步 — 跟随 harness-flow v0.1.0 (pre-release, 2026-04-29)

- 24 SKILL.md 全量内容更新（host-neutral 措辞：`AGENTS.md` → "项目级路径约定"；`templates/foo.md` → 各 skill `references/foo.md` 路径）
- references/ 重组：原 family-level 共享资产分发到各 skill：
  - `review-record-template.md` → 6 个 review skill 各自副本
  - `verification-record-template.md` → `hf-completion-gate` + `hf-regression-gate` 各自副本
  - `finalize-closeout-pack-template.md` → `hf-finalize/references/`
  - `feature-readme-template.md` + `task-progress-template.md` → `hf-specify/references/`
  - `task-board-template.md` → `hf-tasks/references/`
  - `worktree-isolation.md` → `hf-test-driven-dev/references/`
  - `workflow-shared-conventions.md` → `hf-workflow-router/references/`
- 删除 `packs/coding/skills/{docs,templates}/`（10 文件，内容已分发）
- 删除 `packs/coding/principles/`（6 文件；upstream ADR-001 D11："`docs/principles/` is design reference only, not a runtime dependency"）
- 第一方保留：`hf-workflow-router/SKILL.md` step 3.5 + `references/recall-integration.md`（F014 增量）
- 6 skill `evals/evals.json` 测试 prompt 刷新

### v0.3.0 同步

- 新增 1 个 skill：`hf-doc-freshness-gate`（对外可见文档同步 gate；位于 `hf-regression-gate` 之后、`hf-completion-gate` 之前）
- 新增 1 篇 family-level principle：`emergent-vs-upfront-patterns.md`
- 新增 1 个 design 子引用：`hf-design/references/ddd-tactical-modeling.md`

### v0.2.0 同步（Phase 0 初始化）

- 新增 1 个 skill：`hf-experiment`（假设验证 probe，conditional 插入 discovery / spec 阶段）
- 新增 3 篇 family-level principles：`architectural-health-during-tdd.md` / `methodology-coherence.md` / `sdd-artifact-layout.md`
- 新增 1 个 template：`feature-readme-template.md`
- 22 个原有 skill SKILL.md / references/ 全量覆盖更新

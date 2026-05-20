# `packs/code-audit/` — Existing-Code Bug Audit Pack

本 pack 用于**存量代码 bug 审查**：拿到一个仓库（可能很大），按模块切分、双 agent 串行确认、输出 HTML / Excel 报告。

## Pack 概况

| 字段 | 值 |
|---|---|
| `pack_id` | `code-audit` |
| `version` | `0.3.0` |
| `schema_version` | `1` |
| `skills` | 4 |
| `agents` | 2 |

### v0.3.0 新增（Per-Module Independent Context）

- **每模块独立上下文一审**：`audit-reviewer` 每次 invocation 只扫一个模块；orchestrator agent 完成后立刻把控制权移交给用户、要求开新会话续跑下一个模块。彻底规避大 run 中后段模块因上下文堆叠 / 滑窗淘汰导致的命中率下降与 severity 漂移。完整契约见 `skills/audit-reviewer/references/per-module-context-protocol.md`
- **默认 budgets 收紧**：`module_budget_tokens` 30000 → **12000**，`module_budget_files` 20 → **8**；让单模块上下文远低于模型硬上限，给注意力留富余
- **目录树切分（partition strategy 4）**：`audit-planner` 默认按目录递归下钻切模块，命名 `<parent>/<sub>` 保留路径结构；`plan.json` 新增 `partition_strategy` 字段（取值 `agents-md` / `top-level` / `directory-tree` / `hybrid`）
- **`audit-reviewer` 新 Hard Gate**：单次 invocation 最多扫一个模块；同会话连扫多模块视作违反契约
- **`code-audit-reviewer-agent` 新 `--resume` / `--module` / `--auto-loop` 参数**：默认每模块新会话；`--auto-loop` 是 CI 降级模式，会在 audit-log 写 warning
- **完全向后兼容**：0.1.0/0.2.0 时代的 plan.json 仍可直接被 0.3.0 reviewer / renderer 处理；只是 budgets 较宽，建议下次重审时让 planner 重写

### v0.2.0 新增

- **项目 profile 自动识别**：audit-planner Step 0 检测语言 + 架构 + frameworks（嵌入式 / SOA / web / SPA / CLI / 数据 pipeline / generic）
- **针对性 review checklist + 用户确认**：Step 0.5 基于 profile 选 preset，回显给用户确认/调整后再切模块
- **场景预设**：`c-cpp-embedded-soa` / `c-cpp-embedded` / `python-web-service` / `frontend-spa` / `generic`（详见 `skills/audit-reviewer/references/scenario-presets/`），可自定义扩展
- **finding.category 由 checklist 动态决定**：不再是固定 11 类；renderer 软验证 + report header 展示 profile/checklist
- **完全向后兼容**：0.1.0 时代的 plan.json（无 profile/review_checklist 字段）按 base 11 通用 taxonomy 处理

## 与其它 review 相关 skill 的边界

| 相关 | 场景 | 与本 pack 区别 |
|---|---|---|
| `packs/coding/skills/hf-code-review/` | PR / commit diff 评审（HF workflow 一环） | 输入是 diff、单 agent、不出报告 |
| `packs/garage/agents/code-review-agent.md` | PR 审查 + 对齐用户 style | 同上，单 agent |
| `packs/coding/skills/hf-bug-patterns/` | 把重复 bug 提炼为长期可复用模式 | 是"沉淀"不是"审查执行" |

本 pack 的差异化关键词：**存量全量代码、模块切分、双 agent 确认、HTML/Excel 报告、可重复执行（每次一个 run-id）**。

## 双 Agent 确认流程（0.3.0 — 每模块独立上下文）

```
用户请求审查 → [会话 1: code-audit-reviewer-agent]
                  1. audit-planner Step 0   识别 profile（语言 + 架构）
                  2. audit-planner Step 0.5 推荐 review_checklist（preset），与用户握手确认
                  3. audit-planner Step 1-4 切模块（默认目录树策略 4）→ plan.json
                  4. audit-reviewer  扫【一个】模块出 finding 草稿（category ∈ review_checklist）
                  ↓ 移交：开新会话续跑下一模块
              [会话 2: code-audit-reviewer-agent --resume <run_id>]
                  4. audit-reviewer  扫下一个模块 ...
                  ↓
              ... 重复直到 plan.modules 全部 done ...
                  ↓
              [会话 N+1: code-audit-verifier-agent]    (独立上下文，看不到一审推理过程)
                  5. audit-verifier  对每条 finding 独立复核 → confirmed / rejected / upgrade / downgrade / needs_more_evidence
                  6. audit-reporter  汇总并渲染 HTML（含 profile + checklist 头部）+ 可选 Excel
                  ↓
              用户拿到 reports/report.html
```

**为什么两个 agent 而不是同一 agent 两轮**：

- 避免推理污染：verifier 启动时只看 finding 的 `description + evidence + 原代码`，看不到一审内部推理草稿
- 角色分离：reviewer 鼓励"广撒网"；verifier 鼓励"严格、敢于反驳"
- 可追溯：record 清楚记录"谁判了、判了啥、为什么"

**为什么一审还要每模块开新会话**（0.3.0 新增独立性）：

- LLM 上下文有硬上限；一次塞 N 个模块的代码 + finding 草稿会触发宿主或模型的上下文压缩 / 滑窗淘汰
- 被压缩后，靠后的模块审查变成"基于摘要"而非"基于原文"，命中率显著下降，严重度判断也容易跟随前序 finding 漂移
- 新会话保证每个模块都拿到同等的"注意力预算"，与 reviewer↔verifier 的独立性形成完整闭环
- 详见 `skills/audit-reviewer/references/per-module-context-protocol.md`

## Skills

| id | 文件 | 用途 |
|---|---|---|
| `audit-planner` | [`skills/audit-planner/SKILL.md`](skills/audit-planner/SKILL.md) | 切模块清单、定优先级、输出 `plan.json` |
| `audit-reviewer` | [`skills/audit-reviewer/SKILL.md`](skills/audit-reviewer/SKILL.md) | 一审：逐模块扫描代码，出 finding 草稿（带证据） |
| `audit-verifier` | [`skills/audit-verifier/SKILL.md`](skills/audit-verifier/SKILL.md) | 二审：对每条 finding 独立复核 + 必填 `evidence_check` |
| `audit-reporter` | [`skills/audit-reporter/SKILL.md`](skills/audit-reporter/SKILL.md) | 汇总 confirmed findings，渲染 HTML（必需）+ Excel（可选） |

## Agents

| id | 文件 | 用途 |
|---|---|---|
| `code-audit-reviewer-agent` | [`agents/code-audit-reviewer-agent.md`](agents/code-audit-reviewer-agent.md) | 编排 audit-planner + audit-reviewer（一审角色） |
| `code-audit-verifier-agent` | [`agents/code-audit-verifier-agent.md`](agents/code-audit-verifier-agent.md) | 编排 audit-verifier + audit-reporter（二审 + 报告角色） |

## Finding 数据契约（核心）

每条 finding 必须包含：

| 字段 | 必需 | 说明 |
|---|---|---|
| `id` | ✅ | `F-<run-id>-<seq>` 全局唯一 |
| `run_id` | ✅ | 本次审查的 run id |
| `module` | ✅ | 被审模块路径（如 `src/garage_os/runtime/`） |
| `file` | ✅ | 出问题的文件相对路径 |
| `line_start` / `line_end` | ✅ | 行号区间（1-indexed，闭区间） |
| `file_sha256` | ✅ | 审查时文件 sha256（行号漂移告警依据） |
| `title` | ✅ | 一句话标题 |
| `category` | ✅ | 见下面 11 类 bug 分类 |
| `severity` | ✅ | `critical` / `high` / `medium` / `low` / `info` |
| `confidence` | ✅ | `high` / `medium` / `low` |
| `description` | ✅ | 自然语言说明：为什么这是 bug |
| `evidence` | ✅ | `code_snippet`（实际代码）+ `reasoning`（为什么有问题）+ `trigger_conditions`（什么时候触发）+ `expected_vs_actual`（预期 vs 实际）+ `related_files`（旁证） |
| `suggested_fix` | ✅ | 建议如何修 |
| `reviewer` | ✅ | 一审 agent id + 时间戳 |
| `verifier` | ✅ | 二审 status（`confirmed` / `rejected` / `upgrade` / `downgrade` / `needs_more_evidence`）+ `reason` + `evidence_check` |

完整 JSON schema 见 `skills/audit-reviewer/references/finding-schema.md`。

## Bug 分类（scenario-aware）

v0.2.0 起 finding 的合法 category 集合**由 plan.json `review_checklist.categories[]` 决定**，而非固定 11 类。`audit-planner` 在 Step 0/0.5 根据项目 profile 推荐一份 preset，与用户握手确认后落 plan.json。

### Base 11 通用 taxonomy（preset = `generic`，也是无 checklist 时的回退）

| category | 说明 |
|---|---|
| `correctness` | 逻辑错误、off-by-one、边界遗漏 |
| `error-handling` | 异常未捕获、错误吞没、错误码丢失 |
| `concurrency` | 竞态、死锁、共享状态未保护 |
| `resource-leak` | 文件句柄、连接、锁未释放 |
| `security` | 注入、路径穿越、敏感信息泄露、弱加密 |
| `api-misuse` | 第三方 API 用错、弃用 API |
| `typing` | 类型不一致、Optional 未守护 |
| `performance` | 明显的 O(n²)、不必要的 IO、死循环风险 |
| `dead-code` | 不可达分支、未使用函数 |
| `contract-violation` | 违反项目内既有接口契约 / schema |
| `i18n-or-encoding` | 编码、locale 处理错误 |

### 场景 preset（针对性更强的清单）

| preset id | 适用项目 | 关键 category（节选） |
|---|---|---|
| `c-cpp-embedded-soa` | C/C++ 嵌入式 + SOA（AUTOSAR / SOME/IP / DDS / Zenoh） | `memory-safety` / `undefined-behavior` / `isr-safety` / `real-time` / `ipc-contract` / `serialization` / `hardware-resource` / `portability` / `build-and-config` / `coding-standard` |
| `c-cpp-embedded` | C/C++ 嵌入式（单设备 / 非服务化） | 同上，去除 `ipc-contract` / `serialization` |
| `python-web-service` | Python web 服务（FastAPI / Flask / Django） | `input-validation` / `auth-authz` / `sql-injection` / `secrets-and-config` / `async-concurrency` / `database` / `dependency-vuln` / `dos` / `observability` |
| `frontend-spa` | React / Vue / Svelte / Angular 等 SPA | `xss` / `state-management` / `effect-correctness` / `route-and-auth` / `bundle-and-build` / `accessibility` / `network-api` / `secret-leak` |
| `generic` | 未命中具体场景 | 同 base 11 |

详细 preset 文件：`skills/audit-reviewer/references/scenario-presets/<preset-id>.md`，含每类 description / `severity_default` / examples / 二选一仲裁规则。Base 11 详见 `skills/audit-reviewer/references/bug-taxonomy.md`。

### 自定义 preset

复制 `skills/audit-reviewer/references/scenario-presets/_template.md` 改名 → 在 `bug-taxonomy.md §2` 表登记 → 可选在 `audit-planner/references/project-profile-rubric.md` 加命中规则。也可在 Step 0.5 通过 `add <id>:<description>` 临时给一次性 run 加 category。

## 运行数据落盘位置

```
.garage/code-audit/runs/<run-id>/
├── plan.json                       # audit-planner 输出
├── findings/<module>.json          # 一审 finding 草稿
├── verifications/<module>.json     # 二审复核结果
├── confirmed.json                  # 经二审收敛的 finding 全集
├── reports/
│   ├── report.html                 # 必需
│   └── report.xlsx                 # 可选
└── audit-log.jsonl                 # 全程审计流水
```

## 如何使用

### 第 1 步：把 pack 装到你的宿主

在你要审查的项目根目录跑一次 `garage init`：

```bash
# 装到当前项目（project scope，跟项目走，进 git）
garage init --hosts opencode             # 仅 OpenCode
garage init --hosts claude               # 仅 Claude Code
garage init --hosts opencode,claude      # 同时装两家
garage init --hosts all                  # 三家全装（含 Cursor，但 Cursor 无 agent surface，见下）

# 装到用户家目录（user scope，跨项目复用，不入项目 git）
garage init --hosts opencode --scope user
```

落盘位置：

| Host | 安装位置（project scope） | 是否支持 agent surface |
|---|---|---|
| OpenCode | `.opencode/skills/audit-*/SKILL.md` + `.opencode/agent/code-audit-*-agent.md` | ✅ 装到 `.opencode/agent/` |
| Claude Code | `.claude/skills/audit-*/SKILL.md` + `.claude/agents/code-audit-*-agent.md` | ✅ 装到 `.claude/agents/` |
| Cursor | `.cursor/skills/audit-*/SKILL.md` | ❌ Cursor 无 agent surface，agent 文件不装；可手动唤起 skill |

### 第 2 步：在宿主里跑一审

> **重要**：本 pack 的 agent.md 文件是**宿主级 documentation hint**（F011 ADR-D11-3 既定模式），**不**通过 `garage run <agent>` CLI 运行。宿主（OpenCode / Claude Code）在你发出请求时根据 agent 的 `description:` 自动识别并加载它，用宿主自己的 agent runtime 编排。

#### OpenCode 场景

OpenCode 把 `.opencode/agent/<agent>.md` 注册为可调用 agent。在 OpenCode 会话内：

```text
# 方式 A：自然语言（最常见）— OpenCode 根据 agent description 自动匹配
请用 code-audit-reviewer-agent 审查 src/garage_os/runtime/ 模块
# 或更口语化：
帮我扫一遍 src/garage_os/runtime/ 看有没有 bug
```

```text
# 方式 B：@ 提及显式指名
@code-audit-reviewer-agent target=src/garage_os/runtime/
```

```text
# 方式 C：slash 命令
/agent code-audit-reviewer-agent
然后说明你要审查的目标目录
```

**v0.3.0 默认行为**：agent 在第一个会话里完成 `audit-planner`（识别 profile + 切模块）+ 一个模块的 `audit-reviewer`，落产物到 `.garage/code-audit/runs/<run-id>/`，然后输出**移交消息**告诉你在【新会话】用 `--resume <run-id>` 续跑下一模块；所有模块 done 后再输出最终移交消息，指引你在【另一个新会话】启动二审 agent。

```text
# 续跑下一模块（在新对话里）
请用 code-audit-reviewer-agent --resume run audit-2026-05-20-0935 处理下一个模块

# 或显式指定模块
请用 code-audit-reviewer-agent --resume run audit-2026-05-20-0935 --module knowledge/store
```

CI / 脚本场景如果不在意单次审查精度可以用 `--auto-loop`：

```text
请用 code-audit-reviewer-agent 审查 src/ --auto-loop
```

agent 会在同一会话连扫所有模块（速度快但后段模块可能受上下文压缩影响），并在 audit-log 写 warning。

#### Claude Code 场景

Claude Code 把 `.claude/agents/<agent>.md` 当 subagent 加载：

```text
# 方式 A：在主 Claude Code 会话里自然语言唤起
请用 code-audit-reviewer-agent 审查 src/garage_os/runtime/
```

```text
# 方式 B：用 /agents 列出可用 subagent 并选择
/agents
# 在列表里选 code-audit-reviewer-agent
```

行为与 OpenCode 一致：agent 完成后会提示在 fresh context 启动 verifier。

#### Cursor 场景

Cursor 没有 agent surface，所以 `code-audit-*-agent.md` 不会被装到 Cursor。但 4 个 skill（`audit-planner` / `audit-reviewer` / `audit-verifier` / `audit-reporter`）会装到 `.cursor/skills/`，你可以**手动按顺序唤起**：

```text
# 在 Cursor 对话里依次说：
请使用 audit-planner skill 切分 src/garage_os/runtime/ 的模块清单
# 等它产出 plan.json 后：
请使用 audit-reviewer skill 处理 runtime 模块
# 一审完成后开新对话（保证 fresh context）：
请使用 audit-verifier skill 复核 run audit-<id> 的 findings
请使用 audit-reporter skill 渲染报告
```

> Cursor 路径需要你手动管理"两个独立 context"——必须显式开新对话来跑 verifier，否则违反 `audit-verifier/references/independence-protocol.md` 的独立性要求。

### 第 3 步：在新会话里跑二审

一审 agent 完成后给你一个 `run-id`（如 `audit-2026-05-16-0935`）。**关闭当前会话**，在 OpenCode / Claude Code 内**新开一个会话**：

```text
请用 code-audit-verifier-agent 复核 run audit-2026-05-16-0935，输出 html 和 xlsx 报告
```

或：

```text
@code-audit-verifier-agent run_id=audit-2026-05-16-0935 formats=html,xlsx
```

> **为什么要开新会话**：双 agent 设计的核心是 verifier 看不到 reviewer 的"私下推理"，只信任落盘的 finding 字段。同一 context 里跑 verifier 等于让二审看见一审的对话历史，污染独立判断。详见 `skills/audit-verifier/references/independence-protocol.md`。

二审 agent 会跑 `audit-verifier` 复核每条 finding，再 invoke `audit-reporter` 渲染 HTML + Excel 报告。

### 第 4 步：手动渲染报告（如果 agent 没自动跑）

`audit-reporter` skill 背后的实际渲染脚本是两个独立 Python 入口，**任何时候都可以从 shell 直接跑**（agent 也是这么调的）：

```bash
# HTML 报告（必需）
uv run python packs/code-audit/skills/audit-reporter/scripts/render_html.py \
  --workspace . --run-id audit-2026-05-16-0935

# Excel 报告（可选）
uv run python packs/code-audit/skills/audit-reporter/scripts/render_xlsx.py \
  --workspace . --run-id audit-2026-05-16-0935
```

如果你以 user scope 装了 pack，脚本路径在 `~/.opencode/...` / `~/.claude/...`，按宿主表里对应位置查找。

输出：

```
.garage/code-audit/runs/audit-2026-05-16-0935/reports/
├── report.html    # 47 KB 左右，CSS/JS 全 inline，浏览器直接打开
└── report.xlsx    # 4 sheets：Findings / Summary / RunMeta / Rejected
```

### 端到端示例（OpenCode 场景，C/C++ 嵌入式 SOA 项目）

下面是一个完整流程的 user-side 时间线，假设你刚 clone 了一个 AUTOSAR + SOME/IP + FreeRTOS 的 C/C++ 项目想做全量 bug 审查：

```text
$ cd ~/projects/vehicle-domain-controller
$ garage init --hosts opencode
Initialized garage-agent in /Users/me/projects/vehicle-domain-controller/.garage
Installed 42 skills, 5 agents into hosts: opencode

# === OpenCode 会话 1（一审） ===
You: 请用 code-audit-reviewer-agent 审查 src/ 模块的 bug
Agent: [audit-planner Step 0] 识别项目 profile...

       === Detected Project Profile ===
       languages:      c, cpp
       architectures:  embedded, soa
       frameworks:     FreeRTOS, AUTOSAR-Classic, SOME/IP
       risk_focus:     memory-safety, isr-safety, ipc-contract, real-time
       signals:
         - src/board/stm32f4xx_hal_conf.h
         - src/rtos/FreeRTOSConfig.h
         - ipc/proto/*.arxml (12 service contracts)
         - linker script bsp/STM32F407.ld

       === Suggested Review Checklist (preset: c-cpp-embedded-soa) ===
        1. memory-safety        — UAF / double-free / 缓冲区溢出 / OOB / dangling pointer
        2. undefined-behavior   — signed overflow / strict aliasing / 对齐 / NULL deref
        3. isr-safety           — ISR 内阻塞 / 非 reentrant / volatile / 优先级反转
        ... (共 15 类)

       请确认 (ok / del / add / swap-preset / edit)
You: ok

Agent: [audit-planner Step 1-4] 切出 7 个模块清单，写到
       .garage/code-audit/runs/audit-2026-05-16-0935/plan.json
       (含 profile + review_checklist + modules)

Agent: [audit-reviewer] 逐模块扫描 (checklist preset: c-cpp-embedded-soa)...
       module=rtos     完成，12 条 finding（isr-safety=4, memory-safety=3, ...）
       module=ipc      完成，9 条 finding（ipc-contract=5, serialization=2, ...）
       ...
Agent: 一审完成。run_id: audit-2026-05-16-0935
       - 模块数: 7
       - finding 草稿数: 47
       - by_severity: critical=4 high=18 medium=15 low=8 info=2
       - by_category: isr-safety=10 memory-safety=8 ipc-contract=7 ...

       下一步请在【新会话】启动 code-audit-verifier-agent 做独立复核：
       "请用 code-audit-verifier-agent 复核 run audit-2026-05-16-0935，
        输出 html 和 xlsx 报告"

# === 关闭会话 1，OpenCode 内开新会话 ===

# === OpenCode 会话 2（二审 + 报告） ===
You: 请用 code-audit-verifier-agent 复核 run audit-2026-05-16-0935，
     输出 html 和 xlsx 报告
Agent: [audit-verifier] 独立复核 47 条 finding...
       module=runtime: 9 confirmed, 1 rejected, 2 downgrade
       module=knowledge: 7 confirmed, 1 rejected
       ...
Agent: [audit-reporter] 渲染 HTML + Excel...
       reports/report.html (78 KB)
       reports/report.xlsx (24 KB)

       审查完成。Confirmed: 41 / Rejected: 6
       打开 .garage/code-audit/runs/audit-2026-05-16-0935/reports/report.html

# === 离开 OpenCode，浏览器看报告 ===
$ open .garage/code-audit/runs/audit-2026-05-16-0935/reports/report.html
```

### 常见问题

**Q: 一定要分两个会话跑吗？**
A: **强烈建议**。同一个会话里跑 verifier 等于让二审看见一审的中间推理，污染独立判断（详见 `independence-protocol.md`）。如果宿主不支持显式 fresh context，至少要让 verifier 在判决时**只引用 finding 字段而非对话历史**，但这是降级方案。

**Q: 为什么一审 0.3.0 也要每模块新开会话？太麻烦了**
A: 出于审查精度。LLM 上下文有硬上限，一审一次扫 5+ 个模块时，上下文会触发自动压缩/滑窗淘汰，靠后模块的命中率会肉眼可见地降低、severity 判断也跟随前序 finding 漂移。每模块新会话保证每个模块都拿到同等"注意力预算"。如果你确实想"一把跑完"，传 `--auto-loop`（agent 会在 audit-log 写 warning，结果可能受影响，建议事后让 verifier 兜底）。完整解释见 `skills/audit-reviewer/references/per-module-context-protocol.md`。

**Q: 模块切得太细了，看着像"每个文件一个模块"**
A: 0.3.0 默认 budget=token 12000 / files 8，确实比 0.2.0 紧。可以在第一次跑时显式调宽：`module_budget_tokens=20000 module_budget_files=15`。但**不建议**回到 30000/20——那是引发上下文压缩的临界值。中间值（如 16000/10）是较好的折衷。

**Q: agent 不认识 `code-audit-reviewer-agent` 怎么办？**
A: 确认（1）你跑过 `garage init --hosts <你的宿主>`；（2）`.opencode/agent/code-audit-reviewer-agent.md`（或 `.claude/agents/...`）真实存在；（3）宿主在你启动会话后已经重新加载 agent 目录（OpenCode / Claude Code 通常自动；个别情况需要重启会话）。

**Q: 我已经审过一次了，怎么续跑？**
A: 一审 agent 支持 `resume`：在 OpenCode 里说 "请用 code-audit-reviewer-agent --resume run audit-2026-05-16-0935 继续未完成的模块"。agent 会读 `plan.json` 找 `status=pending` 的模块继续。

**Q: 报告里某条 finding 行号不对，源代码改过了？**
A: 报告会在卡片顶部显示 `⚠ file changed since audit, line numbers may have shifted`。如果改动很大，开新 run 重审即可。

**Q: 我的项目没有 Python / openpyxl，xlsx 渲染会失败？**
A: 不会阻断 HTML 渲染。`render_xlsx.py` 默认 lenient 模式，缺 openpyxl 时跳过 xlsx 输出 + 在 stderr 打印提示，HTML 报告照常生成。要硬要求生成 xlsx 时加 `--strict` flag。

## 边界与不变量

- pack 内容物（SKILL.md / agent.md）保持宿主中立（NFR-701）
- `.garage/code-audit/runs/<run-id>/` 是工件目录，不进 memory 子系统（`knowledge/` / `experience/`），不被 F013-A skill mining 当 ExperienceRecord 挖掘
- finding 行号漂移：每条 finding 落盘时记 `file_sha256`，HTML 渲染时若当前文件 sha 已变则在卡片顶部加 "⚠ file changed since audit, line numbers may have shifted" 提示

## 实施切片（cycle 计划）

| Slice | 内容 | 状态 |
|---|---|---|
| A | pack 骨架（4 skill + 2 agent + pack.json + README）+ dogfood 物化验证 | ✅ |
| B | `audit-reporter/scripts/render_html.py` + 模板 + 单测 | ✅ |
| C | `render_xlsx.py` + `openpyxl` 依赖 + 单测 | ✅ |
| D | 端到端 dogfood：审 `src/garage_os/runtime/` + walkthrough；详见 `DOGFOOD-EXAMPLE.md` | ✅ |
| E (v0.2.0) | 项目 profile + review_checklist + scenario presets | ✅ |
| F (v0.3.0) | per-module-context-protocol + 收紧 budgets + 目录树 partition strategy 4 | ✅ |

## Dogfood 参考结果

见 [`DOGFOOD-EXAMPLE.md`](DOGFOOD-EXAMPLE.md)：用本 pack 实际审了 `src/garage_os/runtime/` 模块（2224 LoC），一审出 8 条 finding 草稿、二审独立复核（7 confirmed + 1 downgrade）、产 HTML + Excel 报告。run files 在 `.gitignore` 中（与 `.garage/sessions/` 同策略），不入 git；artifact 在 PR walkthrough 中。

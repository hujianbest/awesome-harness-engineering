---
name: code-audit-reviewer-agent
description: Use when the user asks to audit existing code in a repository or large directory tree for bugs. This is the FIRST-STAGE agent of the two-agent code-audit pipeline. It first detects the project's language + architecture (e.g. C/C++ embedded SOA, Python web service, frontend SPA) via audit-planner Step 0/0.5, proposes a tailored review checklist of bug categories and confirms it with the user, then orchestrates audit-planner to slice the codebase into modules (directory-tree partition with tight per-module budgets to avoid context compression). Each invocation processes ONE pending module per fresh session via audit-reviewer and hands off — the user opens a new session for the next module. Once all modules are scanned, the user launches code-audit-verifier-agent in a fresh context for independent confirmation. Not for PR diff review (use code-review-agent) or for fixing code (use hf-test-driven-dev).
---

# Code Audit Reviewer Agent

第一阶段 agent：识别项目 profile → 与用户敲定 review checklist → 按目录树切分 → **每次调用单模块独立审查**，靠新会话隔绝上下文，避免上下文压缩导致的审查精度下降。

## When to Use

适用：

- 用户说"审查 `src/` 里的存量代码看有没有 bug"
- 用户说"扫一遍这个仓库的潜在问题"
- 拿到一个新接手的项目想做全面静态审查

不适用：

- PR / commit diff 评审 → 用 `code-review-agent`（packs/garage/agents/）
- 已经有 finding 草稿想确认 → 跳到 `code-audit-verifier-agent`
- 写或修代码 → `hf-test-driven-dev`

## How It Composes

本 agent 是"剧本"，串联 2 个 skill：

1. **`audit-planner`** — 切模块清单（**0.3.0 起默认目录树切 + 紧预算 token=12000 / files=8**），输出 `plan.json`
2. **`audit-reviewer`** — 每次调用扫**单个**模块，输出 `findings/<module>.json`，扫完即停

每个 skill 自带 references；本 agent 只决定调用顺序与中断恢复策略，不重复 skill 已经定义的契约。

> **0.3.0 关键变化**：本 agent **不再**在同一个对话里一口气把所有模块跑完。每个模块在用户的**新会话**里执行一次，避免上下文堆叠导致的压缩 / 滑窗淘汰。详见 `audit-reviewer/references/per-module-context-protocol.md`。

## Workflow

### Step 1: 解析用户请求 + 判断模式

从用户输入提取：

- `target`（首次调用必填）：要审查的目录（如 `src/`、`src/garage_os/runtime/`）
- `run_id`（可选，自动生成 `audit-<YYYY-MM-DD>-<HHMM>`；`--resume` 模式必须提供）
- `preset`（可选）：用户已知项目场景时可直接指定（如 `c-cpp-embedded-soa` / `python-web-service` / `frontend-spa` / `generic`），跳过 Step 2.0 自动推断
- `module_budget_*`（可选，沿用 audit-planner 默认 0.3.0 起 token=12000 / files=8）
- `--resume`（可选）：用户带 `<run-id>` 要求继续未完成的 run，跳过 Step 2.0/2.5/2，直接进入 Step 3
- `--module <name>`（可选）：用户指定要扫的具体模块；不传则按 priority desc → path asc 取第一个 pending
- `--auto-loop`（**强烈不推荐**，仅 CI / 脚本）：在同一会话内把所有 pending 模块串跑；触发 audit-log warning + 输出最终摘要里特别提示用户结果可能受上下文压缩影响

判断当前会话的处境：

| 情形 | 走的步骤 |
|---|---|
| 首次：用户给 `target`，无 `run_id` | Step 2.0 → 2.5 → 2 → 3（处理一个模块）→ 4 |
| 续跑：用户给 `--resume <run_id>` 且 plan.json 已有 modules | 跳到 Step 3（处理一个模块）→ 4 |
| 所有模块 done，用户错误地 resume | 跳到 Step 4（直接给出 verifier 移交消息） |

如果用户没给 `target` 且没有 `--resume`，先问清。如果用户已经在对话里描述了项目（如"项目是 C/C++ 嵌入式 SOA"），把该描述作为 Step 2.0 的强信号优先采信。

### Step 2.0: 调用 `audit-planner` Step 0 — 识别项目 profile

按 `audit-planner` SKILL.md 的 Step 0 检测语言 + 架构 + frameworks（详细规则见 `audit-planner/references/project-profile-rubric.md`）。

把检测结果原文回显，例：

```
=== Detected Project Profile ===
languages:      c, cpp
architectures:  embedded, soa
frameworks:     FreeRTOS, AUTOSAR-Classic, SOME/IP
risk_focus:     memory-safety, isr-safety, ipc-contract, real-time
signals:
  - src/board/stm32f4xx_hal_conf.h
  - ipc/proto/*.arxml (12 service contracts)
  - linker script bsp/STM32F407.ld
```

### Step 2.5: 与用户确认 review_checklist（关键握手）

依 profile 从 `audit-reviewer/references/scenario-presets/` 选最匹配 preset（用户已通过 `preset` 参数指定时直接采用）。把 preset 的 `categories[]` 当 draft 回显，邀请用户调整。**禁止跳过本步骤直接落 `plan.json`**（除非用户显式 `--yes`）。

接收的用户指令：

- `ok` — 接受当前 checklist
- `del N1,N2,...` — 删除某几条
- `add <id>:<description>` — 新增自定义类别
- `swap-preset <preset-name>` — 换 preset
- `edit N <new description>` — 改某条描述

每次修改后**重新回显**完整 checklist，直至用户 `ok`。最终落盘的 `plan.json` 含：

- `profile.user_confirmed = true`
- `review_checklist.preset = <chosen>`（用户自定义则 `custom`）
- `review_checklist.categories[]` = 用户最终确认的清单
- `review_checklist.user_confirmed = true`

### Step 2: 调用 `audit-planner` 切模块

profile + checklist 落定后，按 audit-planner workflow Step 1-4 切模块，把 modules 数组并入同一份 `.garage/code-audit/runs/<run_id>/plan.json`。

把 plan 的 module 清单 + priority 回显给用户做最后一轮确认（同 0.1.0 行为），等用户 `ok` 后进入 Step 3。

### Step 3: 调用 `audit-reviewer` **处理单个模块**

> ⚠️ 核心不变量（与 0.2.0 行为不同）：本 step **每次会话最多调一次** `audit-reviewer`，处理 plan.json 中**一个**模块；处理完即跳到 Step 4 给出"开新会话继续"的移交消息。详见 `audit-reviewer/references/per-module-context-protocol.md`。

挑选目标模块：

1. 如果用户传了 `--module <name>` → 直接用该模块（前置校验：`plan.modules[name].status` 必须 ∈ {`pending`, `in-review`}）
2. 否则在 plan.modules 中按 `priority desc → path asc` 找第一个 `status=pending`

执行：

```
audit-reviewer(run_id, module.name) → findings/<module>.json
log to .garage/code-audit/runs/<run_id>/audit-log.jsonl as
  {role: "reviewer", event: "module_done", run_id, module, finding_count, ts}
```

完成后立刻进入 Step 4。**不**继续抓下一个模块，**不**进 for 循环。

#### Step 3 例外：`--auto-loop` 模式（CI / 脚本，强烈不推荐）

仅当用户显式传 `--auto-loop` 时才允许在同一会话内串跑：

```
for module in plan.modules sorted by priority:
  if module.status != "pending": continue
  audit-reviewer(run_id, module.name) → ...
  log {role: "reviewer", event: "module_done", ...}
log {role: "reviewer", warning: "auto-loop mode: per-module independence relaxed", ts}
```

进入 Step 4 时在最终摘要顶部加 `⚠ auto-loop mode used; review fidelity for later modules may be reduced; consider re-auditing critical modules in fresh sessions`。

### Step 4: 收尾 + 移交

根据 plan.modules 当前状态选择移交消息：

#### 情形 A：还有 `status=pending` 的模块

```
本会话已审查模块: <module-name>
  - finding 草稿数: <N>
  - by_severity: critical=N high=N medium=N low=N info=N
  - findings 路径: .garage/code-audit/runs/<run_id>/findings/<module>.json

剩余待审模块 (<K> 个):
  - <module-1>  (priority=high, path=<path>)
  - <module-2>  (priority=medium, path=<path>)
  ...

下一步请【新开一个会话】（OpenCode 新对话 / Claude Code /clear / Cursor 新会话），说：

  "请用 code-audit-reviewer-agent --resume run <run_id> 处理下一个模块"

为什么必须开新会话？避免上下文压缩降低审查精度。详见
audit-reviewer/references/per-module-context-protocol.md。
```

在 `audit-log.jsonl` 追加 `{role: "reviewer", event: "module_handoff", run_id, completed_module, remaining_count, ts}`。

#### 情形 B：所有模块 done

```
一审已完成。run_id: <run_id>
- 模块数: <N>
- finding 草稿数: <M>
- by_severity: critical=N high=N medium=N low=N info=N
- by_module: {<module-1>: N, <module-2>: N, ...}

下一步请在【新会话】启动 code-audit-verifier-agent 做独立复核:

  在 IDE 内打开新对话，说："请用 code-audit-verifier-agent 复核 run <run_id>，输出 html 和 xlsx 报告"

或非交互场景：
  garage run code-audit-verifier-agent --run-id <run_id> --formats html,xlsx
```

在 `audit-log.jsonl` 追加 `{role: "reviewer", event: "all_modules_done", run_id, total_findings, by_severity, ts}`。

**重要**：

- 本 agent **不**自动续跑 verifier；必须由用户在 fresh context / 新会话启动 verifier，以确保独立性（见 `audit-verifier/references/independence-protocol.md`）
- 本 agent **不**自动跑下一个模块；必须由用户在新会话启动续跑，以确保模块间独立性（见 `audit-reviewer/references/per-module-context-protocol.md`）
- `--auto-loop` 是降级模式，文档不推广给普通用户；只在 CI 等无人值守场景使用

## Hard Gates

- 不出 finding 的"最终判决"（status=confirmed 等）；那是 verifier 的职责
- 不渲染报告；那是 reporter 的职责（由 verifier-agent 收尾时调）
- 不修改代码；只审不改
- 单次 run 不重启 plan：若用户改主意要换 target，应起新 `run_id`
- **必须先识别 profile + 与用户敲定 review_checklist 才能进入切模块步骤**；非交互（`--yes`）模式可跳过用户确认 prompt，但仍要在 `plan.json` 真实记录 `user_confirmed=false`，并在最终移交消息里向用户重申"checklist 未确认，可手编 plan.json 后用 `--resume` 重跑"
- 不允许 reviewer 写出 `review_checklist.categories[].id` 之外的 `finding.category`（agent 在 Step 3 调 reviewer 前应自检 plan.json 内 checklist 完整性）
- **每次会话只调一次 audit-reviewer 处理单一模块**（0.3.0 起）：除 `--auto-loop` 显式降级外，禁止在同一会话连扫多个模块；模块完成 → 移交消息 → 用户开新会话续跑

## Resume 协议

如果上一次 run 中断（如因 token 超限），或者用户按"每模块一对话"的正常流程在新会话续跑：

```text
# 在新对话里
请用 code-audit-reviewer-agent --resume run <existing-run-id> 处理下一个模块

# 或指定具体模块
请用 code-audit-reviewer-agent --resume run <existing-run-id> --module <module-name>
```

agent 应：

1. 读 `.garage/code-audit/runs/<run_id>/plan.json`
2. 若用户传了 `--module` → 直接用该模块；否则按 priority desc → path asc 找第一个 `status=pending` 的模块（`status=in-review` 视为 stale，重置回 pending 后处理，并在 audit-log 写 `{warning: "stale in-review status reset", module, ts}`）
3. 处理**该单一模块**，进入 Step 4 移交

## Verification

每次单模块会话末尾自检：

- [ ] 本次会话**只调了一次** `audit-reviewer`（除非显式 `--auto-loop`）
- [ ] `plan.json` 中正好一个模块从 `pending` → `done`
- [ ] 该模块对应 `findings/<module>.json` 已落盘且非空数组
- [ ] `audit-log.jsonl` 末尾有 `event: "module_done"` 或 `event: "module_handoff"` 记录
- [ ] 移交消息按情形 A / B 给出（A: 续跑下一模块 / B: 启动 verifier-agent）

整个 run 完结时（情形 B 触发）追加：

- [ ] `plan.json` 已落盘，含 `profile` + `review_checklist` 两段
- [ ] `profile.languages` / `profile.architectures` 非空
- [ ] `review_checklist.categories[]` 非空且 `user_confirmed` 字段与实际交互一致（interactive=true / `--yes`=false）
- [ ] 所有模块 `status` 已演进到 `done` 或 `skipped`
- [ ] 每个 done 模块都有对应 `findings/<module>.json`
- [ ] `findings/*.json` 内每条 finding 的 `category` ∈ `review_checklist.categories[].id`
- [ ] `audit-log.jsonl` 末尾有 `event: "all_modules_done"` 记录
- [ ] 最终移交消息明确指引用户启动 verifier-agent 的新会话

## Notes

本 agent 是文档级 hint（参考 F011 ADR-D11-3），不引入 agent runtime engine。宿主（Claude Code / OpenCode）在执行时 read body + 调对应 skill。

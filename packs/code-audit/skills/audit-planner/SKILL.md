---
name: audit-planner
description: Use when starting an existing-code bug audit on a repository or large directory tree and you must decide which modules to scan, in what order, and with what per-module token budget. Produces plan.json that downstream audit-reviewer consumes module-by-module. Not for PR diff review (use hf-code-review) or for actually finding bugs (use audit-reviewer).
---

# Audit Planner

把仓库切成可消化的"模块"，给出审查计划。`code-audit-reviewer-agent` 在每轮一审前必须先调用本 skill。

## When to Use

适用：

- 用户请求"审查这个仓库的 bug"、"扫一下 `src/` 的存量代码"
- 一审 reviewer 需要知道"现在应该审哪个模块、按什么顺序"
- 大代码量场景，单次上下文不够装整个仓库

不适用：

- PR diff review → `hf-code-review`
- 已经切好模块、要真正出 finding → `audit-reviewer`
- 写新代码 → `hf-test-driven-dev`

## Hard Gates

- 不读 SKILL.md 描述外的项目代码内容，只看目录结构、文件大小、`AGENTS.md` 模块概览段
- 不出 finding（即便扫目录时已感觉到可疑），只出"审查计划"
- 单模块预算超限必须再切，不允许把超大模块原样塞给 reviewer

## Workflow

### 1. 解析目标

输入参数：

- `target`：必填，要审查的目录（绝对或相对路径，如 `src/`、`src/garage_os/`）
- `run_id`：可选，默认 `audit-<YYYY-MM-DD>-<HHMM>`
- `module_budget_tokens`：可选，默认 30000（单模块期望输入 token 上限）
- `module_budget_files`：可选，默认 20（单模块期望文件数上限）

### 2. 切模块（按优先级依次尝试）

**策略 1：显式约定优先**

读项目根 `AGENTS.md`，若有"模块概览"或类似段落（典型为 Markdown 表格、列含模块名 + 路径），按该清单切。本仓库 `AGENTS.md` 的"garage-agent 开发者参考 > 模块概览"段就是范例。

**策略 2：顶层目录切**

`target/` 第一层子目录每个算一个模块。如 `src/garage_os/{runtime,knowledge,storage,...}`。

**策略 3：聚类切**

若策略 1/2 给出的模块仍超 `module_budget_*`，按"同目录 + 文件数 ≤ K + LoC ≤ M"再切。给出子模块路径，命名约定 `<parent-module>:<sub-name>`。

### 3. 估算每个模块的体量

逐模块统计（不读文件内容，只看文件元数据）：

- `file_count`：该模块下所有 `*.py / *.ts / *.tsx / *.js / *.go / *.rs / *.java / *.kt / *.rb / *.cpp / *.c / *.h / *.cs` 文件数（语言清单可被项目约定覆盖）
- `loc_estimate`：总行数估算（用 `wc -l` 或等价）
- `priority`：高 / 中 / 低，按下列规则：
  - 高：模块涉及 runtime / security / persistence / 用户输入解析
  - 中：knowledge / business logic / API surface
  - 低：types-only / 纯 enum / 纯 dataclass 集合 / 纯 utility

### 4. 写 `plan.json`

落到 `.garage/code-audit/runs/<run_id>/plan.json`，格式见 `references/plan-schema.md`。

返回结构化摘要给 agent：

```
run_id: <run_id>
plan_path: .garage/code-audit/runs/<run_id>/plan.json
module_count: <int>
total_files: <int>
total_loc: <int>
modules: [{name, path, priority, file_count, loc_estimate}, ...]
next_action: audit-reviewer
```

## Output Contract

- 写盘：`.garage/code-audit/runs/<run_id>/plan.json`（不写 finding，不写 verification）
- 返回：`run_id` + `plan_path` + module 清单摘要
- 唯一下一步：`audit-reviewer`（agent 接力时按 priority desc 排队）

## Red Flags

- 模块切得太粗（如把整个 `src/` 当一个模块）→ reviewer 会因 token 超限失败
- 模块切得太细（如每个 `.py` 一个模块）→ 失去模块级关联性 + 报告噪声大
- 不写 `plan.json` 直接返回模块清单 → 中断恢复无依据
- 在 plan 阶段提"我看到 X 文件可能有 bug" → 越权，不是本 skill 的职责
- 忽略 `AGENTS.md` 已声明的模块概览，自己造一套 → 与项目约定漂移

## Verification

- [ ] `plan.json` 已落到 `.garage/code-audit/runs/<run_id>/`
- [ ] 每个模块的 `loc_estimate` 与 `file_count` 已填
- [ ] 每个模块的 `priority` 已分类
- [ ] 单模块 `loc_estimate` 不超 `module_budget_*` 的 1.5 倍（超出必须再切）
- [ ] 返回摘要含 `run_id` + `plan_path` + `next_action=audit-reviewer`

## Reference Guide

| 文件 | 用途 |
|---|---|
| `references/plan-schema.md` | `plan.json` 的 JSON schema + 字段定义 |
| `references/module-partition-rubric.md` | 三策略切分的详细判断规则与边界 |

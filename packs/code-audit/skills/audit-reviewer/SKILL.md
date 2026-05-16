---
name: audit-reviewer
description: Use when scanning an existing-code module for bugs and emitting finding drafts. Reads source files within one module from the plan.json produced by audit-planner, walks files line-by-line, emits findings/<module>.json with file path, line numbers, category, severity, confidence, code snippet evidence, and reasoning. This is the PRIMARY (first-stage) reviewer in the two-agent confirmation pipeline; downstream audit-verifier independently confirms each finding. Not for PR diff review (use hf-code-review) or for verifying findings (use audit-verifier).
---

# Audit Reviewer

一审：在单个模块内逐文件扫代码，出 finding 草稿。每条 finding 必须带证据。

## When to Use

适用：

- `audit-planner` 已写出 `plan.json`，现在要扫某个模块出 finding
- 在 `code-audit-reviewer-agent` 主流程中被调用

不适用：

- 还没切模块 → `audit-planner`
- 二审复核 finding → `audit-verifier`
- PR diff 评审 → `hf-code-review`
- 发现问题想顺手改 → 一律不改；只出 finding

## Hard Gates

- **只审不改**：reviewer 不写源码、不重命名、不调整结构
- **每条 finding 必须有证据**：缺 `evidence.code_snippet` 或缺 `evidence.reasoning` 的 finding 不得落盘
- **一次只审一个模块**：跨模块的发现写为 `related_files`，主 finding 仍归属当前模块
- **行号必须 1-indexed + 闭区间**：`line_start <= line_end`，超出文件总行数为非法
- **不输出 prose review**：不写"这个模块整体来说……"之类的总体评价；只出结构化 finding

## Workflow

### 1. 读取上下文

- 读 `.garage/code-audit/runs/<run_id>/plan.json` 找到目标模块（状态应为 `pending`）
- 把模块 `status` 改为 `in-review`（原子写）
- 读项目根 `AGENTS.md` 获取项目级编码约定（如有）

### 2. 逐文件扫描

对模块内每个源文件：

1. 读全文，记录 `file_sha256`
2. 按 `references/bug-taxonomy.md` 的 11 类逐类扫描
3. 命中即起草一条 finding，按 `references/finding-schema.md` 填齐字段
4. 严重度初判按 `references/severity-rubric.md`
5. confidence 初判：
   - `high`：行内直接可见的问题（如未捕获异常、明显的资源泄漏、明显的边界错误）
   - `medium`：需要跨文件 / 跨函数推理才成立的问题
   - `low`：依赖运行时假设、可能是误报

### 3. 证据收集

每条 finding 的 `evidence` 必须填：

- `code_snippet`：原代码片段（包含问题行 + 上下 2-3 行上下文）
- `reasoning`：为什么这是 bug（不只是"这里写错了"，要说"在 X 条件下会触发 Y 后果"）
- `trigger_conditions`：触发条件（如"并发 archive + read"）
- `expected_vs_actual`：期望 vs 实际行为
- `related_files`：旁证文件（如调用方、同语义但正确的实现）

证据收集的详细标准见 `references/evidence-contract.md`。

### 4. 写盘

- finding 数组写到 `.garage/code-audit/runs/<run_id>/findings/<module>.json`
- finding `id` 用 `F-<run_id>-<seq>` 命名，`<seq>` 在 run 内全局递增（多模块汇总后单调）
- 每条 finding 的 `verifier.status` 字段留空（由 `audit-verifier` 写入），但占位整个 `verifier` 对象用 `{}` 占位
- `reviewer.agent` 写当前 agent id，`reviewer.ts` 写当前 UTC ISO 8601
- 完成后把 plan.json 中该模块的 `status` 改为 `done`

### 5. 返回结构化摘要

```
run_id: <run_id>
module: <module-name>
findings_path: .garage/code-audit/runs/<run_id>/findings/<module>.json
finding_count: <int>
by_severity: {critical: N, high: N, medium: N, low: N, info: N}
by_category: {correctness: N, ...}
next_action: audit-reviewer (next pending module) or audit-verifier (all done)
```

## Output Contract

- 写盘：`findings/<module>.json`（数组，按 line_start 升序）+ 修改 `plan.json` 的 module status
- 不写：`verifications/`、`confirmed.json`、`reports/`（属下游 skill）
- 不动：源码、项目其他文件
- 唯一下一步：若 plan.json 还有 pending 模块则继续 `audit-reviewer`；否则 `audit-verifier`

## Red Flags

- 把"代码风格不一致"当 finding（不在本 pack 范围 → 用 `hf-code-review` + style 偏好）
- finding 描述含 "may be" / "could be" 但没填 `trigger_conditions`
- 同一行多条 finding 拆得过细（建议合成一条复合 finding，类别取主导）
- `evidence.code_snippet` 是手敲的（必须从源文件原样复制）
- 行号写错（off-by-one、把空行算进、把 1-indexed 写成 0-indexed）
- `confidence=high` 但 `evidence.reasoning` 不足 2 句话
- 漏写 `file_sha256`（后续 verifier 无法判断文件是否漂移）
- 在 finding 里写"建议引入新框架重构"（越权；如要重构走 `hf-design` / `hf-increment`）

## Verification

- [ ] `findings/<module>.json` 已落盘
- [ ] 每条 finding 含 `id` / `module` / `file` / `line_start` / `line_end` / `file_sha256` / `category` / `severity` / `confidence` / `description` / `evidence{code_snippet, reasoning, trigger_conditions, expected_vs_actual}` / `suggested_fix` / `reviewer{agent, ts}` / `verifier: {}`（占位）
- [ ] 行号在文件总行数范围内
- [ ] `plan.json` 中该模块 status 已改为 `done`
- [ ] 返回摘要含 `findings_path` + `finding_count` + 按 severity/category 分布

## Reference Guide

| 文件 | 用途 |
|---|---|
| `references/finding-schema.md` | finding JSON schema 完整字段定义 |
| `references/bug-taxonomy.md` | 11 类 bug 分类 + 每类典型例子 |
| `references/evidence-contract.md` | 什么算"证据"、证据强度等级 |
| `references/severity-rubric.md` | severity 5 档判定规则 |

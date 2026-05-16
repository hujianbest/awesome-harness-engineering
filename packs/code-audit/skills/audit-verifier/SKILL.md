---
name: audit-verifier
description: Use as the SECOND-STAGE independent confirmer in the two-agent code-audit pipeline. Reads finding drafts produced by audit-reviewer and independently re-examines each one against the actual source code, writes verifications/<module>.json with status (confirmed/rejected/upgrade/downgrade/needs_more_evidence), reason, and evidence_check. Operates with FRESH context — does not see reviewer's internal reasoning beyond what is recorded in the finding's description+evidence fields, to enable independent judgement. Not for emitting new findings (use audit-reviewer) or rendering the report (use audit-reporter).
---

# Audit Verifier

二审：对一审产生的每条 finding 独立复核，写入 `verifier.{status, reason, evidence_check, ...}`。

## When to Use

适用：

- `audit-reviewer` 已完成所有 pending 模块，`findings/*.json` 已落盘
- 在 `code-audit-verifier-agent` 主流程中被调用

不适用：

- 还没出 finding → `audit-reviewer`
- 渲染报告 → `audit-reporter`
- 想直接修代码 → 不在本 pack 范围

## Hard Gates

- **独立判断**：本 skill 启动时只读 finding 的字段（含 `evidence`），**不读** reviewer 的任何额外推理草稿、对话历史
- **必须填 `evidence_check`**：所有 status 都必须写出实际核对了哪些代码 / 文件 / 行
- **严重度 ≥ medium 的 finding 不允许"confirmed without evidence_check"**：缺 `evidence_check` 视为 `needs_more_evidence`
- **rejected 也要写理由**：不丢弃 finding，保留以备审计
- **不改 `category`**：category 由 reviewer 主导；如认为分类完全错误且无法救，用 `rejected` + 在 reason 中说明
- **不改 `evidence`**：verifier 不替换 reviewer 的证据；如证据不足应给 `needs_more_evidence` 打回

## Workflow

### 1. 读取 finding 清单

- 读 `.garage/code-audit/runs/<run_id>/plan.json` 确认所有模块 status=`done`
- 遍历 `.garage/code-audit/runs/<run_id>/findings/<module>.json`，构造待复核列表

### 2. 逐条复核

对每条 finding：

1. **文件漂移检查**：重算 `file_sha256`，与 finding 内记录的对比
   - 一致：正常复核
   - 不一致：在 `evidence_check` 显式记录"file changed since audit (sha mismatch)"，可继续复核但 `confidence` 不超过原值；高漂移可直接 `needs_more_evidence`
2. **读原代码**：打开 finding 的 `file`，读取 `line_start - 5` 到 `line_end + 5` 的窗口
3. **比对 `code_snippet`**：finding 里的 snippet 是否与原文件一致
   - 不一致 → `rejected`，reason 写 "code_snippet mismatch with source"
4. **比对 `reasoning` 的可达性**：reviewer 给的触发条件是否在代码中真有路径
5. **检查 `related_files`**：打开每个 related_file 核对
6. **作出判断**，落到下列 5 种 status 之一

### 3. 5 种 status 的判定

| status | 何时取 | 必填字段 |
|---|---|---|
| `confirmed` | 证据成立、严重度合理 | `reason` + `evidence_check` |
| `rejected` | 证据不成立、是误报 / code_snippet 对不上 / reasoning 不可达 | `reason`（说明为什么不成立）+ `evidence_check` |
| `upgrade` | finding 成立但 reviewer 低估了严重度 | `reason` + `evidence_check` + `severity_after` |
| `downgrade` | finding 成立但 reviewer 高估了严重度 | `reason` + `evidence_check` + `severity_after` |
| `needs_more_evidence` | 证据不足以判断但也不是明显误报 | `reason` + `evidence_check`（含"什么证据还需补"） |

**重要**：`needs_more_evidence` 在一个 run 内对同一 finding 最多出现 1 次。reviewer 二度补证据后，verifier 必须给出 `confirmed` / `rejected` / `upgrade` / `downgrade` 终态。

### 4. 写盘

- 每个模块的 verifier 结果写到 `.garage/code-audit/runs/<run_id>/verifications/<module>.json`
- verifications 文件结构与 findings 同 schema，但只保留 `id` + 完整 `verifier` 对象（节省体积）
- 此外**也要原地更新** `findings/<module>.json` 内对应 finding 的 `verifier` 字段（让最终 confirmed.json 合并更简单）

### 5. 合并到 confirmed.json

完成所有模块后：

- 把所有 `findings/<module>.json` 内 `verifier.status ∈ {confirmed, upgrade, downgrade}` 的 finding 合并写到 `.garage/code-audit/runs/<run_id>/confirmed.json`
- 对 `upgrade` / `downgrade` 的 finding，把 `severity` 字段更新为 `verifier.severity_after`（保留原 severity 到 `severity_before` 字段）
- `rejected` / `needs_more_evidence` 的 finding **不进** confirmed.json，但保留在 findings/ 与 verifications/ 内作为审计记录

### 6. 返回结构化摘要

```
run_id: <run_id>
modules_verified: <int>
finding_total: <int>
by_status: {confirmed: N, rejected: N, upgrade: N, downgrade: N, needs_more_evidence: N}
confirmed_path: .garage/code-audit/runs/<run_id>/confirmed.json
next_action: audit-reporter
```

## Output Contract

- 写盘：`verifications/<module>.json` + 原地更新 `findings/<module>.json` 的 `verifier` 字段 + `confirmed.json`
- 不写：reports/（属 `audit-reporter`）
- 唯一下一步：`audit-reporter`

## Red Flags

- 没读源文件就给 `confirmed`（橡皮图章）
- 整批 finding 都 `confirmed` 且 `reason` 文字雷同（提示自动化复制粘贴，要求重审）
- 没填 `evidence_check`
- `rejected` 但理由是"我个人不觉得这是 bug"（不是反驳证据）
- 直接修改 reviewer 的 `description` / `evidence`（越权；只在 `verifier.reason` 写自己的判断）
- 改 `category`（不允许）
- `needs_more_evidence` 重复出现 ≥ 2 次（说明 reviewer 补证据失败，应升级为 rejected 或 confirmed，给出明确终态）

## Verification

- [ ] 每个模块都有 `verifications/<module>.json`
- [ ] 每条 finding 的 `verifier` 字段已被填充（不再是 `{}`）
- [ ] 所有 `verifier.status ∈ {confirmed, upgrade, downgrade}` 的 finding 已合并到 `confirmed.json`
- [ ] 所有 finding 的 `verifier.evidence_check` 字段非空
- [ ] severity ≥ medium 且 `confirmed` 的 finding，其 `evidence_check` 含具体核对动作描述（不只是 "verified")
- [ ] 返回摘要含 `by_status` 分布

## Reference Guide

| 文件 | 用途 |
|---|---|
| `references/verifier-rubric.md` | 5 种 status 的详细判定 + 反例 |
| `references/independence-protocol.md` | "独立判断"的具体执行边界 |

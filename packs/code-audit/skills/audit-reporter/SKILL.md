---
name: audit-reporter
description: Use as the FINAL stage of the code-audit pipeline. Reads confirmed.json (output of audit-verifier) and renders a self-contained single-file HTML report (always) and optionally an Excel workbook. The HTML contains summary stats by severity/category/module, filterable finding cards with code snippets and audit trails (reviewer + verifier). Not for emitting findings (use audit-reviewer) or verifying findings (use audit-verifier).
---

# Audit Reporter

汇总确认后的 finding，渲染 HTML（必需）+ Excel（可选）报告。

## When to Use

适用：

- `audit-verifier` 已写出 `confirmed.json`
- 在 `code-audit-verifier-agent` 主流程的收尾被调用

不适用：

- 还没有 `confirmed.json` → 回到 `audit-verifier`
- 想要重新渲染上一次 run 的报告 → 也用本 skill，传 `--run-id`

## Hard Gates

- 不修改 `confirmed.json`、`findings/`、`verifications/`
- 报告必须是**单文件 HTML**，CSS / JS 全部 inline，可离线打开
- Excel 渲染失败（如缺 openpyxl）不阻断 HTML 渲染
- 报告内不暴露源代码全文，只展示 finding `evidence.code_snippet` 字段

## Workflow

### 1. 读取输入

- `.garage/code-audit/runs/<run_id>/plan.json`：拿 run meta + module 清单
- `.garage/code-audit/runs/<run_id>/confirmed.json`：拿确认后的 finding 数组
- 可选 `.garage/code-audit/runs/<run_id>/findings/<module>.json`：用于在报告"被驳回 finding"区展示 `rejected` / `needs_more_evidence` 的 finding 摘要（保持审计完整性）

### 2. 数据校验

- 每条 finding 字段完整性（按 `finding-schema.md`）
- enum 字段值合法（`severity` / `category` / `confidence` / `verifier.status`）
- 行号合理（`line_start <= line_end`）
- 拒绝 enum 拼写错误（防止报告里出现 "HIGH" 与 "high" 同时存在）

校验失败 → 不渲染报告，把错误写到 stderr 并返回错误码。

### 3. 渲染 HTML

调用 `scripts/render_html.py`（Slice B 引入），输出 `.garage/code-audit/runs/<run_id>/reports/report.html`。

HTML 内容契约（详见 `references/report-schema.md`）：

- 顶部 banner：run_id / 时间 / target / pack version
- Summary 区：总 finding 数 / 按 severity 分布饼图（SVG） / 按 category 柱图 / 按 module 表
- Filter 区：severity / category / confidence / module / verifier_status 多选筛选（纯 JS）
- Finding 卡片列表：每条卡片
  - 标题 + severity badge + category badge + confidence badge
  - `<file>:<line_start>-<line_end>` + 复制按钮
  - 代码片段（pre + code，简单高亮）
  - description / evidence / suggested_fix
  - audit trail：reviewer agent + ts → verifier agent + ts + status + reason + evidence_check
- 文件漂移告警：若 finding 的 `file_sha256` 与渲染时 file 当前 sha 不一致，卡片顶部加 ⚠ banner
- 底部："被驳回 finding" 折叠区：列出 `rejected` / `needs_more_evidence` 的 id + 模块 + 理由摘要

### 4. 渲染 Excel（可选）

若调用方传 `--formats html,xlsx` 或 `--xlsx`，调用 `scripts/render_xlsx.py`（Slice C 引入），输出 `report.xlsx`：

- Sheet 1 - **Findings**：每行一条 finding
- Sheet 2 - **Summary**：透视（severity × module）
- Sheet 3 - **RunMeta**：run_id / 起止时间 / 模块清单 / pack 版本 / agent 版本
- Sheet 4 - **Rejected**：被驳回与待补证据的 finding 概览

若 `openpyxl` 未安装：

- HTML 仍正常生成
- Excel 渲染跳过，stderr 写 "openpyxl not available, skipping xlsx output"
- 返回值不视为错误

### 5. 返回结构化摘要

```
run_id: <run_id>
report_paths:
  html: .garage/code-audit/runs/<run_id>/reports/report.html
  xlsx: .garage/code-audit/runs/<run_id>/reports/report.xlsx (or "skipped" / "n/a")
finding_total: <int>
by_severity: {critical: N, high: N, medium: N, low: N, info: N}
by_module: {runtime: N, knowledge: N, ...}
next_action: done
```

## Output Contract

- 写盘：`reports/report.html`（必需）+ `reports/report.xlsx`（可选）
- 不修改：confirmed.json / findings / verifications
- 唯一下一步：`done`（pipeline 结束）

## Red Flags

- HTML 引用外部 CDN（必须 inline）
- 把源代码全文嵌入 HTML（只能用 finding 内已记录的 code_snippet）
- 渲染 Excel 失败导致 HTML 也未生成（应隔离失败）
- 报告里隐藏被驳回 finding（必须保留可见审计区，哪怕折叠）
- 拼错 severity / category 但报告"渲染成功"

## Verification

- [ ] `reports/report.html` 已生成且 ≥ 1 字节
- [ ] HTML 无 `<script src="http..."` / `<link rel="stylesheet" href="http..."` 外链
- [ ] HTML 含 finding 数与 confirmed.json 一致
- [ ] 若调用方要求 xlsx：`reports/report.xlsx` 已生成（或显式标记 skipped 并给原因）
- [ ] 返回摘要含 `report_paths` + `by_severity` 分布

## Reference Guide

| 文件 | 用途 |
|---|---|
| `references/report-schema.md` | HTML / Excel 输出格式契约（Slice B/C 之前确定） |

## Scripts（后续 Slice 引入）

| 文件 | Slice | 用途 |
|---|---|---|
| `scripts/render_html.py` | B | confirmed.json → report.html 渲染脚本 |
| `scripts/render_xlsx.py` | C | confirmed.json → report.xlsx 渲染脚本 |
| `assets/report-template.html` | B | HTML 模板骨架（含 inline CSS 占位） |
| `assets/report-style.css.txt` | B | inline 到 HTML 的 CSS |

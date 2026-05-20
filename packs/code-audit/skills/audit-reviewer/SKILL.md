---
name: audit-reviewer
description: Use when scanning an existing-code module for bugs and emitting finding drafts. Reads source files within one module from the plan.json produced by audit-planner, walks files line-by-line, emits findings/<module>.json with file path, line numbers, category, severity, confidence, code snippet evidence, and reasoning. The set of allowed finding categories is sourced from plan.json's review_checklist (scenario preset such as c-cpp-embedded-soa / python-web-service / frontend-spa / generic) rather than a fixed taxonomy — keep findings scoped to the user-confirmed checklist. This is the PRIMARY (first-stage) reviewer in the two-agent confirmation pipeline; downstream audit-verifier independently confirms each finding. Not for PR diff review (use hf-code-review) or for verifying findings (use audit-verifier).
---

# Audit Reviewer

一审：在单个模块内逐文件扫代码，出 finding 草稿。每条 finding 必须带证据，且 `category` **必须**取自 `plan.json` 的 `review_checklist.categories[].id`。

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
- **每次调用只审一个模块 + 在新会话独立上下文执行**（0.3.0 起强约束）：reviewer 单次 invocation 只允许处理 plan.json 中**一个** `status=pending` 的模块；处理完该模块即返回，不在同一会话内继续抓下一个模块。完整契约见 `references/per-module-context-protocol.md`，违反此约束的"批量串跑"会触发上下文压缩、显著降低后续模块的命中率与判 severity 准确度
- **行号必须 1-indexed + 闭区间**：`line_start <= line_end`，超出文件总行数为非法
- **不输出 prose review**：不写"这个模块整体来说……"之类的总体评价；只出结构化 finding
- **category 严格来自 plan.json `review_checklist`**：finding `category` 必须 ∈ `review_checklist.categories[].id`；不在清单内的疑似问题按 `bug-taxonomy.md §4.3` 处理（改写到最接近 category 并在 reasoning 注明；或暂存到模块返回摘要的 `skipped_findings` 字段建议用户更新 checklist 重审），**禁止**自己造一个清单外的 category 写盘
- **若 `plan.json` 无 `review_checklist`**（旧 plan，0.1.0 时代）：回退到 `bug-taxonomy.md §1` 的 base 11 类，并在返回摘要里提示 `using base 11 universal taxonomy (no review_checklist found)`

## Workflow

### 1. 读取上下文

- 读 `.garage/code-audit/runs/<run_id>/plan.json` 找到目标模块（状态应为 `pending`）
  - 单次 invocation **只挑一个**模块——如果调用方没指定模块名，按 `priority desc → path asc` 取第一个 `status=pending` 的模块
  - **绝不**在同一调用里遍历多个模块（违反 Hard Gate "每次调用只审一个模块"）
- 把模块 `status` 改为 `in-review`（原子写）
- **加载 review_checklist**：从 plan.json 取 `review_checklist.categories[]`，构造 `{id, description, severity_default, examples}` 索引；作为本次扫描的唯一合法 category 集合
  - 若 `review_checklist.user_confirmed=false`：在返回摘要顶部加一行警告 `⚠ review_checklist not user-confirmed; findings will be re-validated on next run`
  - 若 `review_checklist` 字段缺失：回退 base 11 + 警告
- **加载 profile**：读 `profile.risk_focus[]`；命中本类的 finding 起判 severity 提升一档（如本来 medium 提到 high），不超过该 category 的 `severity_default`
- 读项目根 `AGENTS.md` 获取项目级编码约定（如有）
- **不读其它模块的 `findings/*.json`**：保持本会话上下文只跟当前模块相关（per-module-context-protocol §1）

### 2. 逐文件扫描

对模块内每个源文件：

1. 读全文，记录 `file_sha256`
2. 按 `review_checklist.categories[]` 逐类扫描（每个 category 的覆盖面与 examples 直接来自 checklist 文本；若 checklist 指向某 preset 文件，可读对应 `references/scenario-presets/<preset>.md` 获取更详细的 examples 与仲裁规则）
3. 命中即起草一条 finding，按 `references/finding-schema.md` 填齐字段
4. 严重度初判：取 `review_checklist.categories[<id>].severity_default`（缺省 `medium`），再按 `references/severity-rubric.md` 上下调；如该 category 出现在 `profile.risk_focus[]`，起判提升一档
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

### 5. 返回结构化摘要 + 移交

返回摘要后**立即结束本次调用**，把控制权交还 orchestrator / 用户；**不**继续抓下一个模块。

```
run_id: <run_id>
module: <module-name>
checklist_preset: <preset-id>            # e.g. c-cpp-embedded-soa, or "fallback-base-11"
findings_path: .garage/code-audit/runs/<run_id>/findings/<module>.json
finding_count: <int>
by_severity: {critical: N, high: N, medium: N, low: N, info: N}
by_category: {<checklist-id-1>: N, <checklist-id-2>: N, ...}   # 仅出现在 checklist 内的 id
remaining_pending_modules: [<name1>, <name2>, ...]             # plan.json 中仍 pending 的模块
skipped_findings:                        # 可选；checklist 装不下的疑似问题简述
  - {hint: "...", reason: "no matching category in checklist", suggested_category: "..."}
next_action:
  - 若 remaining_pending_modules 非空: "open a NEW SESSION and run: code-audit-reviewer-agent --resume <run_id>"
  - 若 remaining_pending_modules 为空: "open a NEW SESSION and run: code-audit-verifier-agent --run-id <run_id>"
```

> Reviewer 自己**不**在本会话内继续下个模块；orchestrator agent 收到摘要后也只显示移交消息给用户。每模块一对话，是这个 pack 的核心独立性约束。

## Output Contract

- 写盘：`findings/<module>.json`（数组，按 line_start 升序）+ 修改 `plan.json` 的 module status
- 不写：`verifications/`、`confirmed.json`、`reports/`（属下游 skill）
- 不动：源码、项目其他文件
- 唯一下一步：若 plan.json 还有 pending 模块 → 在**新会话** invoke `audit-reviewer`（处理下一个模块）；若都 done → 在**新会话** invoke `audit-verifier`

## Red Flags

- 把"代码风格不一致"当 finding（不在本 pack 范围 → 用 `hf-code-review` + style 偏好）
- finding 描述含 "may be" / "could be" 但没填 `trigger_conditions`
- 同一行多条 finding 拆得过细（建议合成一条复合 finding，类别取主导）
- `evidence.code_snippet` 是手敲的（必须从源文件原样复制）
- 行号写错（off-by-one、把空行算进、把 1-indexed 写成 0-indexed）
- `confidence=high` 但 `evidence.reasoning` 不足 2 句话
- 漏写 `file_sha256`（后续 verifier 无法判断文件是否漂移）
- 在 finding 里写"建议引入新框架重构"（越权；如要重构走 `hf-design` / `hf-increment`）
- `finding.category` 不在 `review_checklist.categories[].id` 内（无论自创还是从 base 11 抄进来）
- `review_checklist.preset = c-cpp-embedded-soa` 但 finding 大量是 `typing` / `i18n-or-encoding`（清单跟项目不匹配；应在返回摘要里 challenge 用户）
- **同一会话连扫多个模块** → 触发上下文压缩 / 滑窗淘汰，后续模块漏检率显著上升；必须每模块开新会话（per-module-context-protocol.md）
- 摘要里写"我在这个模块同时也注意到了模块 X 的问题" → 跨模块联想说明上下文有交叉污染；本模块只出本模块 finding，跨模块建议写到下个模块的会话里
- 处理一个 pending 模块完成后接着把 status=pending 的下一个模块也扫了 → 严重违反 Hard Gate，摘要必须 stop after 单模块

## Verification

- [ ] `findings/<module>.json` 已落盘
- [ ] 每条 finding 含 `id` / `module` / `file` / `line_start` / `line_end` / `file_sha256` / `category` / `severity` / `confidence` / `description` / `evidence{code_snippet, reasoning, trigger_conditions, expected_vs_actual}` / `suggested_fix` / `reviewer{agent, ts}` / `verifier: {}`（占位）
- [ ] 每条 finding 的 `category` 严格属于 `plan.review_checklist.categories[].id`（或回退情形下属于 base 11）
- [ ] 行号在文件总行数范围内
- [ ] `plan.json` 中**只有一个**模块 status 从 `pending` 变 `done`（本次 invocation 的目标模块）
- [ ] 返回摘要含 `findings_path` + `finding_count` + `checklist_preset` + 按 severity/category 分布 + `remaining_pending_modules` + `next_action`（指引开新会话）
- [ ] 本次会话**没有**触碰 `findings/<其它模块>.json` 或读取其它模块的源代码

## Reference Guide

| 文件 | 用途 |
|---|---|
| `references/finding-schema.md` | finding JSON schema 完整字段定义 |
| `references/bug-taxonomy.md` | base 11 universal + scenario preset 索引 |
| `references/scenario-presets/` | `c-cpp-embedded-soa.md` / `c-cpp-embedded.md` / `python-web-service.md` / `frontend-spa.md` / `generic.md` / `_template.md` 等场景预设 |
| `references/evidence-contract.md` | 什么算"证据"、证据强度等级 |
| `references/severity-rubric.md` | severity 5 档判定规则 |
| `references/per-module-context-protocol.md` | **0.3.0 新增** 每模块独立上下文契约（一审跨模块独立性） |

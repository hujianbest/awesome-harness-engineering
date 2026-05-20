---
name: audit-reviewer
description: Use when scanning an existing-code module for bugs and emitting finding drafts. Reads source files within one module from the plan.json produced by audit-planner, walks files line-by-line, emits findings/<module>.json with file path, line numbers, category, severity, confidence, code snippet evidence, and reasoning. The set of allowed finding categories is sourced from plan.json's review_checklist (scenario preset such as c-cpp-embedded-soa / python-web-service / frontend-spa / generic) rather than a fixed taxonomy — keep findings scoped to the user-confirmed checklist. CRITICAL — if plan.json's review_checklist.user_confirmed is false (or review_checklist is missing entirely), this skill MUST halt and ask the user to confirm/edit/restart-planner BEFORE scanning any module. This is the PRIMARY (first-stage) reviewer in the two-agent confirmation pipeline; downstream audit-verifier independently confirms each finding. Not for PR diff review (use hf-code-review) or for verifying findings (use audit-verifier).
---

# Audit Reviewer

一审：在单个模块内逐文件扫代码，出 finding 草稿。每条 finding 必须带证据，且 `category` **必须**取自 `plan.json` 的 `review_checklist.categories[].id`。

> **二次闸门**：本 skill 是 `audit-planner` Step 0.5 握手协议的**兜底**。若 planner 因任何原因（LLM 漏跳、用户走了 `skip handshake` bypass、用了 `--yes`、或读到旧 v0.1.0 plan.json）写出的 `plan.json` 里 `review_checklist.user_confirmed=false` 或 `review_checklist` 缺失，**reviewer 不会直接进入扫描**：它会先停下来跟用户对齐 checklist。详见下文 §"Handshake Re-Gate"。

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
- **category 严格来自 plan.json `review_checklist`**：finding `category` 必须 ∈ `review_checklist.categories[].id`；不在清单内的疑似问题按 `bug-taxonomy.md §4.3` 处理（改写到最接近 category 并在 reasoning 注明；或暂存到模块返回摘要的 `skipped_findings` 字段建议用户更新 checklist 重审），**禁止**自己造一个清单外的 category 写盘
- **若 `plan.json` 无 `review_checklist`** 或 **`review_checklist.user_confirmed=false`**：触发下文 "Handshake Re-Gate"（**不**直接进入扫描）；只有 Re-Gate 闭环后才允许 §Workflow 走

## Handshake Re-Gate（二次闸门, 0.2.1 新增）

`audit-planner` 的 Step 0.5 是握手协议的**第一道闸门**。但 LLM 在实际跑 v0.2.0 时被发现仍会漏跳握手，导致 `plan.json` 写出 `user_confirmed=false`。本 skill 是**第二道闸门**——加载 plan.json 后，若 checklist 不在"用户确认"状态，必须停下来再走一次轻量握手，把控制权交还给用户。

### 触发条件

满足下列**任一**：

1. `plan.review_checklist.user_confirmed == false`
2. `plan.review_checklist` 字段不存在或为 null（v0.1.0 旧 plan）
3. `plan.review_checklist.categories` 为空数组

### Re-Gate 工作流

**第 1 步**：把当前 checklist（或回退 base 11）按下面**严格模板**回显成一条独立消息：

```
=== ⚠ Review Checklist Not User-Confirmed ===
本次 run (run_id=<run_id>) 的 review_checklist 未经用户握手:
- preset:        <c-cpp-embedded-soa | base-11-fallback>
- user_confirmed: false
- 原因:           <"audit-planner 用 --yes bypass 跳过了握手" | "v0.1.0 旧 plan, 无 review_checklist 字段">

=== Current Checklist ===
 1. memory-safety        — UAF / double-free / 缓冲区溢出 / OOB
 2. undefined-behavior   — signed overflow / 对齐 / NULL deref
 ... (完整列出, 不省略)
N. coding-standard       — MISRA-C / CERT-C 严重违反

=== ⏸️ 等待确认 ===
请回复以下任一指令再继续扫描:
- confirm                    — 接受当前 checklist, 把 user_confirmed 改为 true 后开始扫
- del N1,N2,...              — 删除某几条后再 confirm
- add <id>:<description>     — 新增类别后再 confirm
- edit N <description>       — 改描述后再 confirm
- restart-planner            — 重启 audit-planner Step 0.5 重新走完整握手（推荐）
- skip-and-warn              — 不改 checklist 也不改 user_confirmed, 强制开始扫（会在每条 finding 加 warning）
```

**第 2 步**：**立即结束本轮回复**，等用户在下一轮消息里输入指令。**禁止**：

- ❌ 把 module `status` 改为 `in-review`
- ❌ 读任何源文件
- ❌ 写任何 `findings/*.json`

**第 3 步**：用户回复后按表处理：

| 用户回复 | 行为 |
|---|---|
| `confirm` / `ok` / `yes` | 改 plan.json: `review_checklist.user_confirmed=true` + `confirmed_at=<UTC ISO 8601>`；进入下文 §Workflow Step 1 |
| `del / add / edit ...` | 修改 plan.json 的 `review_checklist.categories[]`，写 `user_confirmed=true` + `confirmed_at`，进入 §Workflow Step 1 |
| `restart-planner` | 输出 "请用 audit-planner 重新走 Step 0/0.5 (建议用 `garage run code-audit-reviewer-agent --run-id <run_id> --restart-planning`)"；本次 reviewer 调用结束 |
| `skip-and-warn` | 保留 `user_confirmed=false`，进入 §Workflow Step 1；每条落盘的 finding 在 `evidence.reasoning` 顶部加一行 "⚠ checklist not user-confirmed for this run"；返回摘要顶部加 `gate=skip-and-warn` |
| 其它/没意会 | 友好澄清，再回到本步等 |

### Re-Gate vs Planner Handshake 的区别

| | audit-planner Step 0.5 | audit-reviewer Handshake Re-Gate |
|---|---|---|
| 时机 | 切模块前 | 扫模块前（plan.json 已经存在） |
| 触发 | 总是（除非用户用 bypass 关键词） | 仅当 user_confirmed=false / checklist 缺失 |
| 指令集 | ok / del / add / swap-preset / edit / skip handshake | confirm / del / add / edit / restart-planner / skip-and-warn |
| 副作用 | 写 plan.json（modules + profile + checklist 完整段） | 仅改 plan.json 的 review_checklist 段（不动 modules） |
| 控制权交还 | 是 | 是 |

## Workflow

### 1. 读取上下文

- 读 `.garage/code-audit/runs/<run_id>/plan.json` 找到目标模块（状态应为 `pending`）
- **触发 Handshake Re-Gate 检查**（见上文）：若 `review_checklist.user_confirmed=false` 或缺失，**先做 Re-Gate**，闭环后才继续
- Re-Gate 通过后，把模块 `status` 改为 `in-review`（原子写）
- **加载 review_checklist**：从 plan.json 取 `review_checklist.categories[]`，构造 `{id, description, severity_default, examples}` 索引；作为本次扫描的唯一合法 category 集合
  - 若 Re-Gate 选了 `skip-and-warn`：使用当前 checklist + 在每条 finding 加 warning
  - 若 `review_checklist` 字段缺失且 Re-Gate 选了 skip-and-warn：回退 base 11 + 警告
- **加载 profile**：读 `profile.risk_focus[]`；命中本类的 finding 起判 severity 提升一档（如本来 medium 提到 high），不超过该 category 的 `severity_default`
- 读项目根 `AGENTS.md` 获取项目级编码约定（如有）

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

### 5. 返回结构化摘要

```
run_id: <run_id>
module: <module-name>
checklist_preset: <preset-id>            # e.g. c-cpp-embedded-soa, or "fallback-base-11"
findings_path: .garage/code-audit/runs/<run_id>/findings/<module>.json
finding_count: <int>
by_severity: {critical: N, high: N, medium: N, low: N, info: N}
by_category: {<checklist-id-1>: N, <checklist-id-2>: N, ...}   # 仅出现在 checklist 内的 id
skipped_findings:                        # 可选；checklist 装不下的疑似问题简述
  - {hint: "...", reason: "no matching category in checklist", suggested_category: "..."}
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
- `finding.category` 不在 `review_checklist.categories[].id` 内（无论自创还是从 base 11 抄进来）
- `review_checklist.preset = c-cpp-embedded-soa` 但 finding 大量是 `typing` / `i18n-or-encoding`（清单跟项目不匹配；应在返回摘要里 challenge 用户）
- 读到 `user_confirmed=false` 直接开扫，没走 Handshake Re-Gate → 违反二次闸门契约

## Verification

- [ ] 加载 plan.json 后先做 Handshake Re-Gate 检查（user_confirmed=true → 直通；false 或缺失 → 走 Re-Gate 闭环再继续）
- [ ] `findings/<module>.json` 已落盘
- [ ] 每条 finding 含 `id` / `module` / `file` / `line_start` / `line_end` / `file_sha256` / `category` / `severity` / `confidence` / `description` / `evidence{code_snippet, reasoning, trigger_conditions, expected_vs_actual}` / `suggested_fix` / `reviewer{agent, ts}` / `verifier: {}`（占位）
- [ ] 每条 finding 的 `category` 严格属于 `plan.review_checklist.categories[].id`（或 Re-Gate 选 skip-and-warn 回退情形下属于 base 11）
- [ ] 行号在文件总行数范围内
- [ ] `plan.json` 中该模块 status 已改为 `done`
- [ ] 返回摘要含 `findings_path` + `finding_count` + `checklist_preset` + 按 severity/category 分布

## Reference Guide

| 文件 | 用途 |
|---|---|
| `../audit-planner/references/handshake-protocol.md` | 上游 Step 0.5 握手协议；reviewer 的 Re-Gate 与之共享术语 |
| `references/finding-schema.md` | finding JSON schema 完整字段定义 |
| `references/bug-taxonomy.md` | base 11 universal + scenario preset 索引 |
| `references/scenario-presets/` | `c-cpp-embedded-soa.md` / `c-cpp-embedded.md` / `python-web-service.md` / `frontend-spa.md` / `generic.md` / `_template.md` 等场景预设 |
| `references/evidence-contract.md` | 什么算"证据"、证据强度等级 |
| `references/severity-rubric.md` | severity 5 档判定规则 |

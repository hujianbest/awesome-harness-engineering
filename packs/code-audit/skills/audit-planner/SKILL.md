---
name: audit-planner
description: Use when starting an existing-code bug audit on a repository or large directory tree. CRITICAL — this skill MUST stop and wait for explicit user confirmation of the review_checklist (Step 0.5) BEFORE it slices modules or writes the modules array of plan.json. It first detects project language + architecture (e.g. C/C++ embedded SOA, Python web service, frontend SPA), proposes a tailored review checklist of bug categories, prints it in a "=== ⏸️ 等待确认 ===" block, returns control to the user, and waits for an "ok" / "del N" / "add" / "swap-preset" / "edit N" reply. Only after the user has typed "ok" (or an equivalent confirmation, or an explicit "--yes" / "skip handshake" bypass in the original request) may slicing proceed. Produces plan.json with profile + review_checklist + modules that downstream audit-reviewer consumes module-by-module. Not for PR diff review (use hf-code-review) or for actually finding bugs (use audit-reviewer).
---

# Audit Planner

把仓库切成可消化的"模块"，给出审查计划。`code-audit-reviewer-agent` 在每轮一审前必须先调用本 skill。

本 skill 在切模块**之前**还有两步关键工作：

1. **识别项目编程语言 + 架构**（如 C/C++ 嵌入式 SOA、Python web 服务、frontend SPA）
2. **基于项目 profile 生成针对性的 bug 检视清单（review_checklist）并与用户握手确认**

通用 11 类 bug 分类是基线（base 11），但实际审查时使用的 category 集合**由用户与 LLM 协商后的 `review_checklist` 决定**——比如 C/C++ 嵌入式 SOA 项目会聚焦 memory-safety / undefined-behavior / isr-safety / ipc-contract / real-time 等，而不是宽泛的 11 类。

---

## ⛔ CRITICAL — Handshake before slicing (read this first)

**Step 0.5 必须真正停下来等用户回答，再进入 Step 1 切模块**。不是写文档式的"请确认"，而是真正中止本轮 tool 调用，把控制权交还给用户，等用户在新一轮消息里输入指令。详见 `references/handshake-protocol.md`。

握手没完成（即用户没在对话里显式回 `ok` 或等价指令）之前**禁止**：

- ❌ 写任何 `plan.json` 字段（包括 modules 段、profile.user_confirmed=true、review_checklist.user_confirmed=true）
- ❌ 把 `modules[]` 数组写入 plan.json
- ❌ 进入 Step 1 / 2 / 3 / 4
- ❌ 把"草案 checklist"和"已开始切模块"放在同一条 LLM 回复里

握手可以**跳过的唯一情况**：用户在本轮原始请求里**显式**写了下列任一关键词——

- `--yes` / `-y` / `assume_yes`
- `跳过确认` / `跳过握手` / `skip handshake` / `auto-yes`
- `直接开始` 同时附带了具体 preset id

**不算"显式同意"**：

- 用户只说"审查 X 模块" → 默认请求，不是同意跳过
- LLM/agent 内部判断"我在自动跑" → 没用，agent 无权代用户同意
- 用户描述了项目（"项目是 C/C++ 嵌入式 SOA"） → 这是 profile 提示，不是 checklist 同意

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

- 不读 SKILL.md 描述外的项目代码内容，只看目录结构、文件大小、`AGENTS.md` 模块概览段；profile 推断阶段允许 sniff 少量代表性文件（构建脚本、入口、IDL/proto/arxml、headers），但不做深度分析
- 不出 finding（即便扫目录时已感觉到可疑），只出"审查计划"
- 单模块预算超限必须再切，不允许把超大模块原样塞给 reviewer
- **必须把 detected profile + 推荐的 review_checklist 在 0.5.b 模板里回显, 并在 0.5.c 真正停下来等用户回答, 收到用户 `ok`（或其它修改指令处理完后再次 `ok`）之后才能写 `plan.json` 任何字段**。"我作为 agent 在自动跑"不构成跳过握手的理由——只有用户在原始请求里**显式**写了 0.5.e 列出的 bypass 关键词才允许跳过。`plan.json` 内 `profile.user_confirmed` 与 `review_checklist.user_confirmed` 字段如实记录这次握手实际是否发生

## Workflow

### 0. 识别项目 profile（语言 + 架构）

依 `references/project-profile-rubric.md` 的信号清单做检测（**不读业务代码逻辑，只看 metadata + 少量代表性 header / build / IDL 文件**）：

- **语言**：按文件扩展名直方图取前 N（`.c/.cpp/.h/.hpp` → C/C++；`.py` → Python；`.ts/.tsx` → TypeScript；`.rs` → Rust；`.go` → Go；`.java/.kt` → JVM 等）
- **架构 / 形态**：搜索特征文件 / 目录
  - **embedded**：linker script `*.ld`、startup `*.s/.S`、`Kconfig`、`FreeRTOSConfig.h`、`HAL_*.h`、CMSIS、`*.dts/.dtsi`、vendor SDK 目录（`STM32*Cube*` / `Zephyr` / `nrfx` / `esp_*`）
  - **SOA / 服务化**：IDL / proto 文件（`*.idl/*.proto/*.fidl/*.arxml/*.capnp`）、service registry 配置、AUTOSAR `*.arxml`、Zenoh / DDS / SOME/IP 关键字
  - **web 服务**：`Dockerfile + FastAPI/Flask/Django/Express` 等框架 import、`openapi.yaml`、`pyproject.toml [project.dependencies]`
  - **frontend SPA**：`package.json` 含 react/vue/svelte/angular、`index.html`、`vite.config.*` / `webpack.config.*`
  - **CLI 工具 / library**：`pyproject.toml [project.scripts]` / `Cargo.toml [[bin]]` / 单仓多 crate
- **frameworks / risk_focus**：从 manifest 文件 + 顶层 README / AGENTS.md 摘取（如 `pyproject.toml` deps、`package.json` deps、`CMakeLists.txt` 的 RTOS / middleware 名）

把检测结果组装成 draft profile：

```json
{
  "languages": ["c", "cpp"],
  "architectures": ["embedded", "soa"],
  "frameworks": ["FreeRTOS", "AUTOSAR-Classic"],
  "build_systems": ["cmake"],
  "risk_focus": ["memory-safety", "isr-safety", "ipc-contract", "real-time"],
  "detected_signals": [
    "src/board/stm32f4xx_hal_conf.h",
    "src/rtos/FreeRTOSConfig.h",
    "ipc/proto/*.arxml (12 service contracts)",
    "linker script bsp/STM32F407.ld"
  ]
}
```

### 0.5. 🛑 HANDSHAKE — 生成 review_checklist, 回显, 然后 STOP

这是整个 skill 里**最容易被错误跳过**的一步。完整流程见 `references/handshake-protocol.md`（含 GOOD vs BAD 例子）。

#### 0.5.a 选 preset + 装载 draft checklist（不写盘）

依 detected profile，从 `../audit-reviewer/references/scenario-presets/` 选最匹配的 preset（如 `c-cpp-embedded-soa.md` / `python-web-service.md` / `frontend-spa.md`）；多 architecture 命中时按"风险面更大"取主导（embedded + soa 优先 embedded-soa；web + cli 优先 web）。

把 preset 的 categories 在内存里组装成 draft `review_checklist`（**这一步不写 plan.json，不写任何其它文件**）。

#### 0.5.b 按严格模板回显 + 显式"等待确认"段

把 draft 用下面**严格模板**打印成 **一条** 消息：

```
=== Detected Project Profile ===
languages:      <c, cpp>
architectures:  <embedded, soa>
frameworks:     <FreeRTOS, AUTOSAR-Classic, SOME/IP>
risk_focus:     <memory-safety, isr-safety, ipc-contract, real-time>
signals:
  - <src/board/stm32f4xx_hal_conf.h>
  - <src/rtos/FreeRTOSConfig.h>
  - <ipc/proto/*.arxml (12 service contracts)>
  - <linker script bsp/STM32F407.ld>

=== Suggested Review Checklist (preset: <c-cpp-embedded-soa>) ===
 1. memory-safety        — UAF / double-free / buffer overflow / OOB / dangling pointer / uninit read
 2. undefined-behavior   — signed overflow / strict aliasing / type punning / alignment / null deref
 3. isr-safety           — ISR 内阻塞调用 / 非 reentrant API / 缺 volatile / 优先级反转
 ... (完整列举所有 categories, 不省略)
N. coding-standard       — MISRA-C / CERT-C / AUTOSAR C++14 严重违反（仅高风险条款）

=== ⏸️ 等待确认 ===
请回复以下任一指令再继续:
- ok                                — 接受当前 checklist, 开始切模块 + 扫描
- del N1,N2,...                     — 删除某几条（按序号）
- add <id>:<description>            — 新增自定义类别
- swap-preset <preset-name>         — 切换 preset
- edit N <new description>          — 改某条描述
- skip handshake                    — 强制跳过握手, 直接用当前 checklist（会标记 user_confirmed=false）
```

#### 0.5.c 🛑 STOP — 立刻结束本轮 tool 调用

**回显完上面这条消息后，必须立即结束本轮回复**，不再调任何工具。控制权完全回到用户。

判断"我是不是真的停下了"的 self-check：

1. 我有没有在同一条回复里既输出 `=== ⏸️ 等待确认 ===` 又紧接着说"已开始切模块"或"audit-reviewer 正在扫 module=X"？如果是，错。
2. 我有没有在用户没有回 `ok` / `del` / `add` / `swap-preset` / `edit` / `skip handshake` 之前就调了任何写盘工具（写 plan.json / findings/）？如果是，错。
3. 我有没有在用户原始请求里实实在在地看到了 `--yes` / `-y` / `跳过确认` / `skip handshake` / `auto-yes` 等 bypass 关键词？没有就必须等。

#### 0.5.d 用户回复后的处理（在下一轮消息里做）

下一轮用户消息进来后按指令处理：

| 用户回复 | 行为 |
|---|---|
| `ok` / `确认` / `yes` / `好的` / `开始` | draft 落 plan.json: `user_confirmed=true` + `confirmed_at=<UTC ISO 8601>`；进入 Step 1 切模块 |
| `del N1,N2,...` | 从 draft 删除对应序号 → 回到 0.5.b 重新回显 → 0.5.c 再 STOP |
| `add <id>:<description>` | 把新 category 追加到 draft → 回到 0.5.b 重新回显 → 0.5.c 再 STOP |
| `swap-preset <name>` | 换 preset 的 categories → 回到 0.5.b 重新回显 → 0.5.c 再 STOP |
| `edit N <description>` | 把第 N 条 description 改写 → 回到 0.5.b 重新回显 → 0.5.c 再 STOP |
| `skip handshake` / `--yes` | draft 落 plan.json: `user_confirmed=false`（如实记录）；进入 Step 1，但在最终返回摘要里加 ⚠ 提示用户 |
| 其它 / 没意会 | 友好澄清"我需要你回复 ok / del / add / swap-preset / edit / skip handshake 之一才能继续"，然后**继续等** |

#### 0.5.e 唯一允许跳过 0.5.c 的情况（"显式 bypass"）

只有当用户在本轮**原始请求**里写了下列任一关键词，才允许直接走 Step 1（仍把 `user_confirmed=false` 如实写入）：

- `--yes` / `-y` / `assume_yes`
- `跳过确认` / `跳过握手` / `skip handshake` / `auto-yes`
- `直接开始` 同时附带了具体 preset id（如"直接用 c-cpp-embedded-soa 开始"）

**注意以下情况不算 bypass**：

- "我在自动模式下运行" / "我是 agent" → 不算（agent 没有同意权）
- "项目是 C/C++ 嵌入式 SOA" → 只是 profile 信号，不是同意 checklist
- "审查 X 模块" → 默认请求，不是同意

### 1. 解析目标

输入参数：

- `target`：必填，要审查的目录（绝对或相对路径，如 `src/`、`src/garage_os/`）
- `run_id`：可选，默认 `audit-<YYYY-MM-DD>-<HHMM>`
- `module_budget_tokens`：可选，默认 30000（单模块期望输入 token 上限）
- `module_budget_files`：可选，默认 20（单模块期望文件数上限）
- `preset`：可选，跳过 Step 0.5 的 LLM 推断，直接采用指定 preset（如 `c-cpp-embedded-soa`、`python-web-service`、`frontend-spa`、`generic`）
- `assume_yes`：可选，跳过 Step 0.5 的用户确认 prompt（CI / 脚本场景）

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

落到 `.garage/code-audit/runs/<run_id>/plan.json`，格式见 `references/plan-schema.md`。**必须**带上 Step 0 / 0.5 产出的 `profile` 与 `review_checklist`。

返回结构化摘要给 agent：

```
run_id: <run_id>
plan_path: .garage/code-audit/runs/<run_id>/plan.json
profile: {languages, architectures, frameworks}
review_checklist: {preset, category_count, user_confirmed}
module_count: <int>
total_files: <int>
total_loc: <int>
modules: [{name, path, priority, file_count, loc_estimate}, ...]
next_action: audit-reviewer
```

## Output Contract

- 写盘：`.garage/code-audit/runs/<run_id>/plan.json`（含 `profile` + `review_checklist` + `modules`；不写 finding，不写 verification）
- 返回：`run_id` + `plan_path` + profile / checklist 摘要 + module 清单摘要
- 唯一下一步：`audit-reviewer`（agent 接力时按 priority desc 排队，并把 `review_checklist.categories` 作为唯一允许的 `finding.category` 来源）

## Red Flags

- 模块切得太粗（如把整个 `src/` 当一个模块）→ reviewer 会因 token 超限失败
- 模块切得太细（如每个 `.py` 一个模块）→ 失去模块级关联性 + 报告噪声大
- 不写 `plan.json` 直接返回模块清单 → 中断恢复无依据
- 在 plan 阶段提"我看到 X 文件可能有 bug" → 越权，不是本 skill 的职责
- 忽略 `AGENTS.md` 已声明的模块概览，自己造一套 → 与项目约定漂移
- 在 0.5.b 回显 checklist 后**同一条消息里**接着说"已开始切模块"或"audit-reviewer 正在扫"→ 没有真正停在 0.5.c
- 用户没回 `ok` 就把 `modules[]` 写进 plan.json → 跳过握手
- 跳过 Step 0.5 用户确认却写 `user_confirmed=true` → 严重违反握手契约（即使是 `--yes` bypass 也应写 `false`）
- 把"我作为 agent 在自动跑"当成跳过握手的理由 → 不允许，只有用户原始请求里 0.5.e 列出的 bypass 关键词才允许
- 用户描述了项目（"是 C/C++ 嵌入式 SOA"）就跳过 0.5.c 直接落 `user_confirmed=true` → 描述 ≠ 同意 checklist
- 用户已经明确说"项目是 C/C++ 嵌入式 SOA"还采用 `generic` preset → 无视用户输入
- review_checklist 与项目 profile 严重不匹配（如 Python web 服务却用 `c-cpp-embedded-soa` preset）→ 必须在回显时显式 challenge

## Verification

- [ ] **本次会话至少出现过一次"在 0.5.b 回显 checklist → 0.5.c STOP → 用户在下一轮消息里回 ok/del/add/swap-preset/edit/skip handshake"的回合**（或用户原始请求里有 0.5.e 列出的 bypass 关键词）
- [ ] `plan.json` 已落到 `.garage/code-audit/runs/<run_id>/`
- [ ] 每个模块的 `loc_estimate` 与 `file_count` 已填
- [ ] 每个模块的 `priority` 已分类
- [ ] 单模块 `loc_estimate` 不超 `module_budget_*` 的 1.5 倍（超出必须再切）
- [ ] `plan.profile` 含 `languages` / `architectures` / `risk_focus` 三个非空字段
- [ ] `plan.review_checklist.categories[]` 非空，每项含 `id` + `description`
- [ ] `profile.user_confirmed` / `review_checklist.user_confirmed` 与实际交互一致：用户回 `ok` → `true` + `confirmed_at` 填；用户走 0.5.e bypass → `false` + `confirmed_at` 不填
- [ ] 返回摘要含 `run_id` + `plan_path` + profile/checklist 摘要 + `next_action=audit-reviewer`；若 `user_confirmed=false` 摘要里附 ⚠ 提示

## Reference Guide

| 文件 | 用途 |
|---|---|
| `references/handshake-protocol.md` | **必读**：Step 0.5 握手的完整脚本、GOOD vs BAD 例子、anti-pattern cheatsheet、验证清单 |
| `references/plan-schema.md` | `plan.json` 的 JSON schema + 字段定义（含 `profile` + `review_checklist`） |
| `references/module-partition-rubric.md` | 三策略切分的详细判断规则与边界 |
| `references/project-profile-rubric.md` | 语言 + 架构识别信号清单（embedded / SOA / web / SPA / CLI 等）|
| `../audit-reviewer/references/bug-taxonomy.md` | 基础 11 类 universal taxonomy + preset 引用 |
| `../audit-reviewer/references/scenario-presets/` | 场景预设清单：`c-cpp-embedded-soa.md` / `python-web-service.md` / `frontend-spa.md` / `_template.md` |

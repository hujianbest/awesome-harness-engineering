---
name: audit-planner
description: Use when starting an existing-code bug audit on a repository or large directory tree. First detects project language + architecture (e.g. C/C++ embedded SOA, Python web service, frontend SPA), proposes a tailored review checklist (scenario-specific bug categories) for user confirmation, then slices the codebase into modules within a per-module token budget. Produces plan.json with profile + review_checklist + modules that downstream audit-reviewer consumes module-by-module. Not for PR diff review (use hf-code-review) or for actually finding bugs (use audit-reviewer).
---

# Audit Planner

把仓库切成可消化的"模块"，给出审查计划。`code-audit-reviewer-agent` 在每轮一审前必须先调用本 skill。

本 skill 在切模块**之前**还有两步关键工作：

1. **识别项目编程语言 + 架构**（如 C/C++ 嵌入式 SOA、Python web 服务、frontend SPA）
2. **基于项目 profile 生成针对性的 bug 检视清单（review_checklist）并与用户确认**

通用 11 类 bug 分类是基线（base 11），但实际审查时使用的 category 集合**由用户与 LLM 协商后的 `review_checklist` 决定**——比如 C/C++ 嵌入式 SOA 项目会聚焦 memory-safety / undefined-behavior / isr-safety / ipc-contract / real-time 等，而不是宽泛的 11 类。

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
- **必须把 detected profile + 推荐的 review_checklist 显式回放给用户、等待确认/修改后才能写 `plan.json`**（除非显式 `--yes` 自动接受）。`plan.json` 内 `profile.user_confirmed` 与 `review_checklist.user_confirmed` 字段记录这次握手

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

### 0.5. 生成 review_checklist 并与用户确认

依 detected profile，从 `../audit-reviewer/references/scenario-presets/` 选最匹配的 preset（如 `c-cpp-embedded-soa.md` / `python-web-service.md` / `frontend-spa.md`）；多 architecture 命中时按"风险面更大"取主导（embedded + soa 优先 embedded-soa；web + cli 优先 web）。

把 preset 的 categories 装载为 draft `review_checklist`，**回显给用户**：

```
=== Detected Project Profile ===
languages:      c, cpp
architectures:  embedded, soa
frameworks:     FreeRTOS, AUTOSAR-Classic
risk_focus:     memory-safety, isr-safety, ipc-contract, real-time
signals:
  - src/board/stm32f4xx_hal_conf.h
  - src/rtos/FreeRTOSConfig.h
  - ipc/proto/*.arxml (12 service contracts)
  - linker script bsp/STM32F407.ld

=== Suggested Review Checklist (preset: c-cpp-embedded-soa) ===
 1. memory-safety        — UAF / double-free / buffer overflow / OOB / dangling pointer / uninit read
 2. undefined-behavior   — signed overflow / strict aliasing / type punning / alignment / null deref
 3. isr-safety           — ISR 内阻塞调用 / 非 reentrant API / 缺 volatile / 优先级反转
 4. concurrency          — RTOS 任务间共享状态无锁 / 双锁顺序 / 信号量错用
 5. real-time            — 时序超 deadline / 看门狗未喂 / 长循环阻塞调度
 6. resource-management  — 堆未释放 / mutex/semaphore 未归还 / 句柄泄露 / 初始化顺序错
 7. error-handling       — 返回值未检 / errno 未处理 / 异常路径吞错
 8. ipc-contract         — SOA IDL 字段不匹配 / 版本兼容 / 序列化端序 / 必填字段缺失
 9. hardware-resource    — 寄存器访问顺序 / DMA / cache 一致性 / 时钟门控错配
10. security             — 外部输入未做长度/边界校验 / 弱密钥 / TOCTOU
11. portability          — endianness 假设 / sizeof 假设 / packed struct ABI
12. build-and-config     — 编译宏配置错 / 链接顺序 / FPU/MPU 选项与硬件不符
13. dead-code            — 不可达分支 / 仅 debug 路径误入 release
14. contract-violation   — header 与 impl 漂移 / AUTOSAR/RTE 契约不符
15. coding-standard      — MISRA-C / CERT-C / AUTOSAR C++14 严重违反（仅高风险条款）

请确认 (按一行一条):
- type [ok]  接受全部
- type [del N1,N2,...]  删除某几条
- type [add <id>:<description>]  新增自定义类别
- type [swap-preset <preset-name>]  切换 preset
- type [edit N <new description>]  改某条描述
```

**等用户回答后才落 plan.json**。用户的修改写入 draft，重复显示直至 `ok`；落盘时：

- `review_checklist.preset = "<chosen-preset>"`（用户自定义则 `"custom"`）
- `review_checklist.categories[]` = 最终用户确认的列表
- `review_checklist.user_confirmed = true`
- `review_checklist.confirmed_at = <UTC ISO 8601>`
- 同步 `profile.user_confirmed = true` + `profile.confirmed_at`

非交互场景（`--yes` / agent 自动模式）：跳过确认，直接采用 preset 默认 checklist，但仍把 `user_confirmed=false` 写入并在返回摘要里提示用户事后可手编 `plan.json` 重跑 reviewer。

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
- 跳过 Step 0.5 用户确认却写 `user_confirmed=true` → 严重违反握手契约
- 用户已经明确说"项目是 C/C++ 嵌入式 SOA"还采用 `generic` preset → 无视用户输入
- review_checklist 与项目 profile 严重不匹配（如 Python web 服务却用 `c-cpp-embedded-soa` preset）→ 必须在回显时显式 challenge

## Verification

- [ ] `plan.json` 已落到 `.garage/code-audit/runs/<run_id>/`
- [ ] 每个模块的 `loc_estimate` 与 `file_count` 已填
- [ ] 每个模块的 `priority` 已分类
- [ ] 单模块 `loc_estimate` 不超 `module_budget_*` 的 1.5 倍（超出必须再切）
- [ ] `plan.profile` 含 `languages` / `architectures` / `risk_focus` 三个非空字段
- [ ] `plan.review_checklist.categories[]` 非空，每项含 `id` + `description`
- [ ] 交互模式下 `profile.user_confirmed=true` 与 `review_checklist.user_confirmed=true`；`--yes` 模式下两者为 `false`（如实记录）
- [ ] 返回摘要含 `run_id` + `plan_path` + profile/checklist 摘要 + `next_action=audit-reviewer`

## Reference Guide

| 文件 | 用途 |
|---|---|
| `references/plan-schema.md` | `plan.json` 的 JSON schema + 字段定义（含 `profile` + `review_checklist`） |
| `references/module-partition-rubric.md` | 三策略切分的详细判断规则与边界 |
| `references/project-profile-rubric.md` | 语言 + 架构识别信号清单（embedded / SOA / web / SPA / CLI 等）|
| `../audit-reviewer/references/bug-taxonomy.md` | 基础 11 类 universal taxonomy + preset 引用 |
| `../audit-reviewer/references/scenario-presets/` | 场景预设清单：`c-cpp-embedded-soa.md` / `python-web-service.md` / `frontend-spa.md` / `_template.md` |

# `plan.json` Schema

`audit-planner` 输出工件，写到 `.garage/code-audit/runs/<run-id>/plan.json`。

## 顶层结构

```json
{
  "schema_version": 1,
  "run_id": "audit-2026-05-16-0435",
  "target": "src/",
  "created_at": "2026-05-16T04:35:12Z",
  "profile": {
    "languages": ["c", "cpp"],
    "architectures": ["embedded", "soa"],
    "frameworks": ["FreeRTOS", "AUTOSAR-Classic", "SOME/IP"],
    "build_systems": ["cmake"],
    "risk_focus": ["memory-safety", "isr-safety", "ipc-contract", "real-time"],
    "detected_signals": [
      "src/board/stm32f4xx_hal_conf.h",
      "src/rtos/FreeRTOSConfig.h",
      "ipc/proto/*.arxml (12 service contracts)",
      "linker script bsp/STM32F407.ld"
    ],
    "user_confirmed": true,
    "confirmed_at": "2026-05-18T08:31:02Z"
  },
  "review_checklist": {
    "preset": "c-cpp-embedded-soa",
    "categories": [
      { "id": "memory-safety",       "description": "UAF / double-free / buffer overflow / OOB / dangling pointer / uninit read" },
      { "id": "undefined-behavior",  "description": "signed overflow / strict aliasing / type punning / alignment / null deref" },
      { "id": "isr-safety",          "description": "ISR 内阻塞调用 / 非 reentrant API / 缺 volatile / 优先级反转" },
      { "id": "concurrency",         "description": "RTOS 任务间共享状态无锁 / 双锁顺序 / 信号量错用" },
      { "id": "real-time",           "description": "时序超 deadline / 看门狗未喂 / 长循环阻塞调度" },
      { "id": "resource-management", "description": "堆未释放 / mutex/semaphore 未归还 / 句柄泄露 / 初始化顺序错" },
      { "id": "error-handling",      "description": "返回值未检 / errno 未处理 / 异常路径吞错" },
      { "id": "ipc-contract",        "description": "SOA IDL 字段不匹配 / 版本兼容 / 序列化端序 / 必填字段缺失" },
      { "id": "hardware-resource",   "description": "寄存器访问顺序 / DMA / cache 一致性 / 时钟门控错配" },
      { "id": "security",            "description": "外部输入未做长度/边界校验 / 弱密钥 / TOCTOU" },
      { "id": "portability",         "description": "endianness 假设 / sizeof 假设 / packed struct ABI" },
      { "id": "build-and-config",    "description": "编译宏配置错 / 链接顺序 / FPU/MPU 选项与硬件不符" },
      { "id": "dead-code",           "description": "不可达分支 / 仅 debug 路径误入 release" },
      { "id": "contract-violation",  "description": "header 与 impl 漂移 / AUTOSAR/RTE 契约不符" },
      { "id": "coding-standard",     "description": "MISRA-C / CERT-C / AUTOSAR C++14 严重违反（仅高风险条款）" }
    ],
    "user_confirmed": true,
    "confirmed_at": "2026-05-18T08:31:02Z"
  },
  "budgets": {
    "module_budget_tokens": 30000,
    "module_budget_files": 20
  },
  "modules": [
    {
      "name": "runtime",
      "path": "src/garage_os/runtime/",
      "priority": "high",
      "file_count": 8,
      "loc_estimate": 1842,
      "languages": ["python"],
      "status": "pending",
      "notes": "Contains session lifecycle + state machine + error handler — runtime correctness critical."
    }
  ],
  "total_files": 64,
  "total_loc": 12459
}
```

## 字段定义

### Top level

| 字段 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `schema_version` | ✅ | `int` | 当前固定为 `1` |
| `run_id` | ✅ | `str` | 本次审查的唯一 ID（推荐 `audit-<YYYY-MM-DD>-<HHMM>`） |
| `target` | ✅ | `str` | 用户请求的审查目标（原样保留） |
| `created_at` | ✅ | `str` | ISO 8601 UTC |
| `profile` | ❌ | `object` | 项目 profile（语言+架构+frameworks+risk_focus）。**0.2.0 起新增；旧 plan.json 缺失时下游按 `generic` 处理** |
| `review_checklist` | ❌ | `object` | 本次审查使用的 bug category 清单（preset 或自定义）。**0.2.0 起新增；旧 plan.json 缺失时 reviewer + renderer 回退 base 11 类** |
| `budgets` | ✅ | `object` | 单模块预算约束 |
| `modules` | ✅ | `array` | 模块清单，至少 1 项 |
| `total_files` | ✅ | `int` | 所有模块 file_count 之和 |
| `total_loc` | ✅ | `int` | 所有模块 loc_estimate 之和 |

### `profile`（v0.2.0 新增）

由 `audit-planner` Step 0 检测、Step 0.5 经用户确认后落盘。详细识别规则见 `project-profile-rubric.md`。

| 字段 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `languages` | ✅ | `array<str>` | 主要语言 lowercase（如 `["c", "cpp"]`），按文件数排序 |
| `architectures` | ✅ | `array<str>` | 形态枚举：`embedded` / `soa` / `web` / `frontend` / `cli` / `ml-pipeline` / `library` / `generic`，可多选 |
| `frameworks` | ❌ | `array<str>` | 命中的 framework / middleware（如 `FreeRTOS`、`AUTOSAR-Classic`、`FastAPI`） |
| `build_systems` | ❌ | `array<str>` | 构建系统（如 `cmake` / `cargo` / `poetry` / `npm`） |
| `risk_focus` | ✅ | `array<str>` | 本次审查的着重点（reviewer 起判 severity 时加权），如 `memory-safety` / `ipc-contract` |
| `detected_signals` | ❌ | `array<str>` | 触发 architecture 推断的具体 file / pattern 旁证（≤ 10 条） |
| `user_confirmed` | ✅ | `bool` | Step 0.5 用户是否显式确认（`--yes` 自动模式下 `false`） |
| `confirmed_at` | ❌ | `str` | ISO 8601 UTC，仅当 `user_confirmed=true` 时必填 |

### `review_checklist`（v0.2.0 新增）

| 字段 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `preset` | ✅ | `str` | 选用的 preset id（如 `c-cpp-embedded-soa` / `python-web-service` / `frontend-spa` / `generic` / `custom`） |
| `categories` | ✅ | `array<object>` | 允许出现在 finding 的 category 全集（至少 1 项；reviewer 严格按本清单填 `finding.category`） |
| `categories[].id` | ✅ | `str` | category 唯一 id（kebab-case 推荐，如 `memory-safety`） |
| `categories[].description` | ✅ | `str` | 一句话说明本 category 覆盖的问题面 |
| `categories[].severity_default` | ❌ | `str` enum | reviewer 命中本类时的起判 severity（`critical` / `high` / `medium` / `low` / `info`），缺省 `medium` |
| `categories[].examples` | ❌ | `array<str>` | 典型 bug 示例（≤ 3 条），辅助 reviewer 召回 |
| `user_confirmed` | ✅ | `bool` | Step 0.5 用户是否显式确认 |
| `confirmed_at` | ❌ | `str` | ISO 8601 UTC，仅当 `user_confirmed=true` 时必填 |

**Reviewer / renderer 一致性契约**：

- `audit-reviewer` 写 finding 时，`finding.category` 必须 ∈ `review_checklist.categories[].id`；不在清单内的 finding 直接拒收。
- `audit-reporter`（HTML / XLSX）渲染时：
  - 若 `plan.review_checklist` 存在：使用 `categories[].id` 作为该 run 的合法 category 集合（拒绝其它）
  - 若 `plan.review_checklist` 缺失（旧 plan.json）：回退到 base 11 类（见 `../../audit-reviewer/references/bug-taxonomy.md`）

### 旧 plan.json 兼容

`schema_version` 不变（仍为 1）。`profile` 与 `review_checklist` 都是 optional；缺失时下游：

- reviewer 提示 "this plan has no review_checklist; using base 11 universal taxonomy"
- renderer 按 base 11 验证
- 这保证了 0.1.0 时代的 run 仍可用 0.2.0 renderer 渲染（dogfood / 历史数据兼容）

### `budgets`

| 字段 | 必需 | 类型 | 默认 | 说明 |
|---|---|---|---|---|
| `module_budget_tokens` | ✅ | `int` | `30000` | 单模块期望输入 token 上限 |
| `module_budget_files` | ✅ | `int` | `20` | 单模块期望文件数上限 |

### `modules[]`

| 字段 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `name` | ✅ | `str` | 模块名（如 `runtime`，子模块用 `runtime:sub-name`） |
| `path` | ✅ | `str` | 模块根目录相对仓库根的路径 |
| `priority` | ✅ | `str` enum | `high` / `medium` / `low` |
| `file_count` | ✅ | `int` | 该模块下源码文件数 |
| `loc_estimate` | ✅ | `int` | 总行数估算 |
| `languages` | ✅ | `array<str>` | 主要语言（lowercase，如 `["python"]`） |
| `status` | ✅ | `str` enum | `pending` / `in-review` / `done` / `skipped` |
| `notes` | ❌ | `str` | 切分理由或风险提示 |

## status 演进

- `pending` — `audit-planner` 写入时初始状态
- `in-review` — `audit-reviewer` 接手时改写
- `done` — `audit-reviewer` 完成 finding 草稿后改写
- `skipped` — 用户显式跳过 / 路径不存在 / 文件全部为二进制

`audit-reviewer` 修改本字段时使用原子写（先写 `plan.json.tmp` 再 rename），不破坏其他字段。

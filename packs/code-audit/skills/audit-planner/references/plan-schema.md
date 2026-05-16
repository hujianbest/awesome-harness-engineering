# `plan.json` Schema

`audit-planner` 输出工件，写到 `.garage/code-audit/runs/<run-id>/plan.json`。

## 顶层结构

```json
{
  "schema_version": 1,
  "run_id": "audit-2026-05-16-0435",
  "target": "src/garage_os/",
  "created_at": "2026-05-16T04:35:12Z",
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
| `budgets` | ✅ | `object` | 单模块预算约束 |
| `modules` | ✅ | `array` | 模块清单，至少 1 项 |
| `total_files` | ✅ | `int` | 所有模块 file_count 之和 |
| `total_loc` | ✅ | `int` | 所有模块 loc_estimate 之和 |

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

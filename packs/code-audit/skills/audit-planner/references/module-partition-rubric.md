# Module Partition Rubric

`audit-planner` 切模块的三策略详细规则。

## 策略 1：显式约定优先

读项目根 `AGENTS.md`，识别"模块概览"段。常见特征：

- Markdown 表格，列含 `模块` / `module` / `path` / `routine`
- 段落标题含 "模块"、"module overview"、"architecture"

**当 `AGENTS.md` 同时声明多套清单时**，按下列优先级：

1. "模块概览"或 "Module Overview" 标题段
2. "代码结构"或 "Code Structure"
3. 目录树（fallback，作为策略 2 的输入）

若 `AGENTS.md` 缺失或没有相关段，跳到策略 2。

## 策略 2：顶层目录切

`target/` 第一层子目录每个算一个模块。常见目录：

- Python：`src/<pkg>/<subpkg>/`
- TS / JS：`src/<feature>/`、`packages/<name>/src/`
- Go：`internal/<feature>/`、`cmd/<binary>/`
- Rust：`crates/<name>/src/`

**忽略以下目录**（不当模块）：

- 测试目录：`tests/`、`test/`、`__tests__/`、`*_test.go`
- 文档：`docs/`、`doc/`
- 构建产物：`build/`、`dist/`、`target/`、`node_modules/`、`venv/`、`.venv/`
- 隐藏目录：`.*/`（如 `.git/`、`.github/`）
- 资产：`assets/`、`static/`、`public/`

## 策略 3：超预算后再切

若策略 1 或 2 给出的模块超预算（`file_count > module_budget_files * 1.5` 或 `loc_estimate > module_budget_tokens * 4`，按平均 4 字符/token 估算），按下列规则再切：

1. **二级目录优先**：模块内部若有 ≥ 2 个子目录，每个子目录算一个子模块，命名 `<parent>:<sub-name>`
2. **同前缀文件聚类**：若仅一层文件，按文件名前缀分组（如 `session_*.py` 一组）
3. **强制 cap**：若仍超预算，按文件大小排序，每攒到 `module_budget_files` 个文件分一组，命名 `<parent>:part-N`

## 优先级判定

| 关键词 / 路径 | priority |
|---|---|
| `runtime/`、`auth/`、`security/`、`crypto/`、`payment/`、`database/`、`storage/` | `high` |
| `parser/`、`validator/`、`sanitizer/`（用户输入解析） | `high` |
| `knowledge/`、`api/`、`handlers/`、`controllers/`、`services/`、`adapter/` | `medium` |
| `business logic`、`workflow/`、`orchestrat*/` | `medium` |
| `types/`、`models/`（纯 dataclass / enum 集合） | `low` |
| `utils/`、`helpers/`、`constants/`、`fixtures/` | `low` |

判定无法落到上表时默认 `medium`。

## 估算 LoC

不打开文件内容，用文件大小 / 平均行宽估算：

```
loc_estimate ≈ sum(file_size_bytes for f in module) / 40
```

40 字节 / 行是中文混合 Python 的典型经验值；TS / Go 项目可调到 30。准确的 LoC 不重要，只用来"决定要不要再切"。

## 边界情况

- **空目录**：`file_count=0` 直接跳过，不入 `modules[]`
- **全是二进制 / 数据文件**：识别为 fixture，`status=skipped`，`notes` 写明
- **单文件模块**：合法（如 `src/garage_os/cli.py` 自成一模块），不强行合并
- **超大单文件**（> 2000 LoC）：仍作为一个模块，不切单文件，notes 提示 reviewer 注意

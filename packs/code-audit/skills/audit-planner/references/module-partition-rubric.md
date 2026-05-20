# Module Partition Rubric

`audit-planner` 切模块的四策略详细规则。

> **0.3.0 关键变化**：默认 budgets 从 `tokens=30000 / files=20` 收紧到 `tokens=12000 / files=8`，并新增**策略 4 深度目录树切分**作为默认推荐。配套约束见 `../../audit-reviewer/references/per-module-context-protocol.md`——每个模块都会在 reviewer 新会话内独立审查。

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

## 策略 3：超预算后再切（同前缀文件聚类）

若策略 1 或 2 给出的模块超预算（`file_count > module_budget_files * 1.5` 或 `loc_estimate > module_budget_tokens * 4`，按平均 4 字符/token 估算），且模块**内部没有更多子目录**可下钻：

1. **同前缀文件聚类**：按文件名前缀分组（如 `session_*.py` 一组、`state_*.py` 一组），命名 `<parent>:<prefix>`
2. **强制 cap**：若仍超预算，按文件大小排序，每攒到 `module_budget_files` 个文件分一组，命名 `<parent>:part-N`，并在 `notes` 写明 `partition: file-bucket; reviewer should pay attention to cross-file coupling`

> 当模块内部有子目录时优先走策略 4（深度目录树），策略 3 是"叶子目录"的兜底。

## 策略 4：深度目录树切（0.3.0 默认推荐）

> **当默认 budget 收紧后，绝大多数中等规模 repo 都需要落到本策略**。reviewer 后续会在每模块独立会话内执行（参见 `../../audit-reviewer/references/per-module-context-protocol.md`），所以"模块=明确的目录子树"是最理想的形态。

算法（伪代码）：

```python
def partition_directory_tree(target, budgets):
    candidates = [target]                      # 起点：用户给的根
    final_modules = []
    while candidates:
        d = candidates.pop()
        files = scan_source_files_one_level(d)  # 只看本目录直接挂载的源文件
        subdirs = list_subdirs(d)               # 子目录列表（剔除 tests/ docs/ build/ ...）
        loc = estimate_loc(files)
        nfile = len(files)
        # 情况 A：当前目录单独就装得下且没有子目录 → 落为模块
        if not subdirs and nfile <= budgets.files * 1.5 and loc <= budgets.tokens * 4:
            final_modules.append(make_module(d, files))
            continue
        # 情况 B：当前目录有子目录,本级也有自己的源文件
        # 先把本级直接挂载的文件作为一个 "<dir>:_root" 子模块（若数量 > 0）
        if files:
            if loc_of(files) <= budgets.tokens * 4:
                final_modules.append(make_module(d, files, name=f"{d}:_root"))
            else:
                # 本级文件本身就超预算 → 落到策略 3 同前缀聚类
                final_modules.extend(prefix_cluster(d, files, budgets, name=f"{d}:_root"))
        # 然后把每个子目录递归入栈
        for sub in subdirs:
            candidates.append(sub)
        # 情况 C：当前目录无子目录但超预算 → 走策略 3
        if not subdirs and (nfile > budgets.files * 1.5 or loc > budgets.tokens * 4):
            final_modules.extend(prefix_cluster(d, files, budgets, name=d))
    return final_modules
```

实战要点：

1. **从用户给的 `target` 开始向下递归**，每层都判定"是否单独装得下"
2. **同时含子目录与本级源文件**的目录拆为 "`<parent>:_root`" + 各子目录递归（避免本级文件淹没在父模块）
3. **测试 / 文档 / 构建产物目录**按策略 2 的忽略表跳过
4. **最大深度**：建议 ≤ 4 层；超过 4 层仍超预算的极端情况按策略 3 兜底
5. **命名约定**：用斜杠保留路径（如 `runtime/state-machine`），便于报告头部展示模块树

`partition_strategy` 字段的取值规则：

| 实际走的策略 | 字段值 |
|---|---|
| 仅策略 1 命中且全部模块 < 预算 | `agents-md` |
| 策略 2 顶层目录每个独立装下 | `top-level` |
| 主要靠策略 4 递归切 | `directory-tree` |
| 策略 1 + 策略 4 混合（AGENTS.md 模块部分超预算后再下钻） | `hybrid` |

返回摘要 `partition_strategy` 字段记录主导策略，方便 reviewer / 报告判断"模块边界是否清晰"。

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
- **超大单文件**（> 800 LoC，0.3.0 起从 2000 下调）：仍作为一个模块，不切单文件；`notes` 写 `oversized-single-file: review may suffer accuracy loss; consider refactoring before audit`，`oversized_modules` 摘要包含该项让用户提前知情

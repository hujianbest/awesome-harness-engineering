# Scenario Preset Template — `<preset-id>`

> 复制本文件改名为 `<preset-id>.md` 即可。`<preset-id>` 必须是 kebab-case，与 `bug-taxonomy.md` 表格中登记的 id 一致。

## When to Use

一句话：满足下列**任意 ≥ 1** 条时，`audit-planner` 在 Step 0.5 推荐本 preset：

- （命中条件 1）
- （命中条件 2）
- （命中条件 3）

## Categories

| id | description | severity_default | examples |
|---|---|---|---|
| `<category-1>` | （一句话覆盖面）| medium | （bug 例 1）；（bug 例 2）；（bug 例 3） |
| `<category-2>` | … | high | … |

**注**：`severity_default` 表示 reviewer 命中该类时**起判**的 severity（具体每条 finding 仍可根据 `severity-rubric.md` 上下调），而非"最高"或"最低"。

## 二选一仲裁规则（preset 内部）

若同一问题落多 category：

- `<cat-A>` vs `<cat-B>` → `<cat-A>` 优先（因为 …）
- …

## 不收 base 11 中的哪些 category（如有）

- 显式说明本 preset **未包含** base 11 中的哪些类，原因 1-2 句。例如 `frontend-spa` preset 不收 `concurrency`（单线程 event loop 模型下意义有限）。

## risk_focus 建议

`audit-planner` 在 `profile.risk_focus[]` 默认追加：

- `<risk-1>`
- `<risk-2>`

## 参考资料

- （行业标准 / 既有工具 / 文档链接）

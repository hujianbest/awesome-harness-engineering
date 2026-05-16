# Evidence Contract

每条 finding 必须有证据。本文定义"什么算证据"。

## 证据强度三档

| 等级 | 信号 | 默认 confidence | 例 |
|---|---|---|---|
| **直接证据** | 在源码当行 / 当函数即可看出问题 | `high` | 未捕获异常、明显边界错误、明显资源泄漏、明显死代码 |
| **跨范围证据** | 需要看调用方 / 旁支文件才能确认 | `medium` | 并发竞态、API 契约违反、跨模块状态错位 |
| **运行时假设证据** | 依赖运行时条件，无法静态确认 | `low` | "可能在 PG 14+ 版本变慢"、"如果用户输入超大字符串可能 OOM" |

## 必填证据字段

1. `code_snippet`：**从源文件原样复制**的代码片段
   - 必须包含问题所在的行
   - 必须包含上下 2-3 行上下文，便于 verifier 和报告读者理解
   - 不允许手敲或意译；不允许只贴函数签名而省略 body
   - 长函数可只贴问题段，省略段用 `# ...` 注明（保留所在函数签名）

2. `reasoning`：**至少 2 句话**说明为什么这是 bug
   - 句 1：直接陈述什么地方错了
   - 句 2：陈述错的后果（在什么场景下会出问题）
   - 含跨文件推理时，引用 `related_files` 里的路径，便于 verifier 复核

3. `trigger_conditions`：**触发条件**
   - "在并发 archive 时"、"在用户输入 > 1MB 时"、"在该 if 分支恰好为 False 时"
   - 若条件是"任何调用路径"，写 "always"
   - 若条件不可静态确定，写"runtime condition: X"

4. `expected_vs_actual`：**期望 vs 实际**
   - expected: 一句话，依据是项目约定 / 函数文档 / 类型注解 / 通用最佳实践
   - actual: 一句话，依据是当前实现的实际行为

5. `related_files`（可选但强烈建议）：**旁证文件清单**
   - 调用方 / 实现方 / 同语义但正确的对照实现 / 相关测试
   - 用 `path:line` 或 `path` 表示
   - verifier 优先核对这里列出的文件

## 不算证据的"理由"

下列内容**不能**作为唯一证据（即不能写在 `reasoning` 里作为单独支撑）：

- "我觉得这里有问题"
- "这里 looks suspicious"
- "通常这么写不好"
- 通用编程口号（"don't use global state"、"avoid mutable defaults"）—— 必须落到具体行的具体后果
- 风格 / 命名争议
- "这里没有测试" —— 不是 bug 本身的证据；可以作为 confidence 调低的理由

## confidence 调档规则

| 触发 | 行动 |
|---|---|
| `reasoning` 引用了 `related_files` 中真实存在的代码且行为可推断 | confidence 至少 `medium` |
| `reasoning` 给出运行时反例（"我读 X 测试发现 Y 路径"），但 verifier 复核可能反驳 | confidence `medium` |
| `reasoning` 完全基于"通常这么写不好"或"看起来" | confidence `low`，且建议 reviewer 自审是否撤回该 finding |
| `category=security` 且 `confidence < medium` | 建议 reviewer 强补 `related_files`（security finding 不能凭感觉） |
| `category=performance` 且无 benchmark 数据 | confidence 上限 `medium` |

## 让 verifier 容易复核

`reasoning` + `related_files` 的设计目标：让 verifier 拿到这条 finding 后能在 ≤ 5 分钟内独立判断是否成立。如果 verifier 必须读 10 个文件 + 跑测试才能复核，说明本 finding 的证据收集不够。

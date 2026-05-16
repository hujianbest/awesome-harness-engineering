# Severity Rubric

severity 5 档判定规则。

| 档 | 触发标准 | 例 |
|---|---|---|
| `critical` | 安全漏洞、数据丢失、数据损坏、生产服务不可用风险 | SQL 注入、密钥明文打印到日志、用户数据可被任意覆盖 |
| `high` | 主流程功能错误、明显的崩溃路径、影响多用户 | 主接口在边界条件下抛未捕获异常、并发竞态会让状态错乱 |
| `medium` | 边缘场景错误、性能退化、错误处理不完善 | 罕见输入下 off-by-one、循环内重复 IO 让 P99 翻倍 |
| `low` | 局部小 bug、影响有限、有 workaround | 单元函数返回 `None` 而文档说返回 `int`，但调用方都判了 None |
| `info` | 不是 bug 但值得记录的信号 | 不可达分支、可移除的 dead-code、可改进的轻微 typing 问题 |

## 调档原则

- `category=security`：基础档至少 `medium`；涉及实际可利用漏洞（注入 / 越权 / 凭据泄漏）一律 `critical` 或 `high`
- `category=correctness` 且影响主流程：至少 `high`
- `category=concurrency` 且会破坏一致性：至少 `high`
- `category=resource-leak` 且在主循环 / 高频路径：至少 `medium`
- `category=dead-code` / `typing` 通常 `low` 或 `info`，除非引发别的 bug

## 调高调低的可见条件

| 条件 | 调整 |
|---|---|
| 触发条件极罕见（"用户传入恰好 65536 长度的字符串"） | -1 档 |
| 触发条件常见（"每次启动都走"） | +1 档 |
| 有现成的运行时证据（已知 issue / 已知崩溃日志） | +1 档 |
| 无静态 / 运行时旁证、纯启发式 | -1 档 |
| 已经有 try/except 兜底但未正确处理 | -1 档（不是裸 crash，但仍是 bug） |

## verifier 调档边界

`audit-verifier` 可以 `upgrade` / `downgrade` 一条 finding 的 severity，但：

- 必须填 `severity_after` 字段
- 必须在 `reason` 中说明调档依据
- 调档不影响 `category`（category 由 reviewer 主导，verifier 不改 category，只能 reject）

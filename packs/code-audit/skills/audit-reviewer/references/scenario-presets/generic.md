# Scenario Preset — `generic`

未命中具体场景（embedded / soa / web / frontend / cli / ml-pipeline 全没命中），或用户显式要求"通用审查"时使用。本 preset 就是 `bug-taxonomy.md` §1 的 base 11 直接展开。

## When to Use

`audit-planner` 在 Step 0.5 推荐本 preset，当满足：

- `profile.architectures = ["generic"]`
- 或用户在 Step 0.5 显式 `swap-preset generic`

## Categories

| id | description | severity_default | examples |
|---|---|---|---|
| `correctness` | 逻辑错误、off-by-one、边界遗漏 | high | 循环少跑一次；条件取反；空数组未处理 |
| `error-handling` | 异常未捕获、错误吞没、错误码丢失 | medium | `except: pass` 吞所有；返回值未检；异常类型过宽 |
| `concurrency` | 竞态、死锁、共享状态未保护 | high | 全局 dict 多线程修改无锁；双锁顺序不一致 |
| `resource-leak` | 文件 / 连接 / 锁 / FD 未释放 | medium | `open()` 后异常未关；`acquire()` 后 early-return |
| `security` | 注入、路径穿越、敏感信息泄露、弱加密 | high | SQL 拼接；`../` 未净化；密码 plain-text log；MD5 用于签名 |
| `api-misuse` | 第三方 API 用错、弃用 API、版本不兼容 | medium | `requests` 不设 timeout；deprecate 方法 |
| `typing` | 类型不一致、Optional 未守护 | low | 函数声明 `int` 但分支返回 `None` |
| `performance` | 明显 O(n²)、不必要的 IO、死循环风险 | medium | 内层循环重复 `db.query`；`while True:` 无退出 |
| `dead-code` | 不可达分支、未使用函数、condition 永真/永假 | low | `if False:`；import 未使用；TODO 占位 |
| `contract-violation` | 违反项目内既有接口契约、schema 不匹配 | medium | impl 签名与 protocol 不符；JSON schema 字段拼写错 |
| `i18n-or-encoding` | 编码、locale 处理错误 | low | 强制 ASCII 解码非 ASCII；`str(bytes)` 不指定编码 |

## 二选一仲裁规则

见 `bug-taxonomy.md` §4.1。

## risk_focus 建议

无（generic 不预设 risk_focus；用户可在 Step 0.5 自由追加）。

## 参考资料

- 各语言通用 best practices
- OWASP Top 10（如涉及 web）

# Bug Taxonomy — 11 类

`audit-reviewer` 的 finding `category` 必须取自下表。

| category | 说明 | 典型例子 |
|---|---|---|
| `correctness` | 逻辑错误、off-by-one、边界遗漏 | 循环少跑一次、条件取反、空数组未处理 |
| `error-handling` | 异常未捕获、错误吞没、错误码丢失 | `except: pass` 吞所有异常、未检查返回值、异常类型过宽 |
| `concurrency` | 竞态、死锁、共享状态未保护 | 全局 dict 多线程修改无锁、双锁顺序不一致 |
| `resource-leak` | 文件句柄、连接、锁未释放 | `open()` 后异常未关闭、`acquire()` 后 early-return 未 release |
| `security` | 注入、路径穿越、敏感信息泄露、弱加密 | SQL 拼接、`../` 未净化、密码 plain-text log、MD5 用于签名 |
| `api-misuse` | 第三方 API 用错、弃用 API、版本不兼容 | `requests` 不设 timeout、用了被 deprecate 的方法 |
| `typing` | 类型不一致、Optional 未守护 | 函数声明返回 `int` 但分支返回 `None`、类型注解与实际不一致 |
| `performance` | 明显的 O(n²)、不必要的 IO、死循环风险 | 内层循环重复 `db.query`、`while True:` 无退出条件 |
| `dead-code` | 不可达分支、未使用函数、condition 永真/永假 | `if False:`、import 但未使用、TODO 留了 5 年的占位函数 |
| `contract-violation` | 违反项目内既有接口契约、schema 不匹配 | 实现签名与 protocol 不符、JSON schema 字段拼写错误 |
| `i18n-or-encoding` | 编码、locale 处理错误 | 强制 ASCII 解码非 ASCII 输入、`str(bytes)` 不指定编码 |

## 边界与去重规则

### 一条 finding 一个 category

不允许 `category=["correctness", "error-handling"]`。若问题在多个 category 维度都成立，按"哪个维度后果更严重"取主导：

| 二选一场景 | 优先取 |
|---|---|
| security vs others | `security` |
| correctness vs typing（运行时 vs 编译时） | `correctness` |
| concurrency vs error-handling（并发触发的异常） | `concurrency` |
| resource-leak vs error-handling（异常路径漏关闭） | `resource-leak` |
| performance vs correctness | `correctness`（如果会算错） / `performance`（如果只是慢） |

### 不入分类的"问题"（不要写成 finding）

- 代码风格 / 命名 / 缩进 → 不在本 pack 范围（用 `hf-code-review` + STYLE 偏好）
- 缺测试 / 测试覆盖度 → `hf-test-review`
- 文档缺失 / 注释不全 → `hf-traceability-review`
- 架构 / 模块边界违反 → `hf-code-review` CR7 / `hf-design-review`
- "感觉以后可能要重构" → 不出 finding（reviewer 不做建议性意见）

### 跨语言通用性

上表 11 类对 Python / TS / Java / Go / Rust 等主流语言通用。语言专属习语（如 Rust 的生命周期错误）归到最接近的语义类，必要时在 `evidence.reasoning` 内补语言相关注释。

## 相关 skill 切换

- `hf-bug-patterns`：若同一类问题在多 run 中反复出现（≥ N 次），考虑用 `hf-bug-patterns` 沉淀为可复用模式（本 pack 不直接做沉淀，只出当前 finding）

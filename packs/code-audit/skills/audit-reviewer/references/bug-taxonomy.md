# Bug Taxonomy

`audit-reviewer` 在写 `finding.category` 时**必须**使用 plan.json `review_checklist.categories[].id` 列出的 id。本文档说明：

1. **base 11 universal categories**（preset = `generic` 时的默认全集，也是历史兼容回退）
2. **scenario presets**（`audit-planner` 在 Step 0.5 根据项目 profile 推荐）
3. **如何扩展自定义 preset**

## 1. Base 11 Universal Categories（preset = `generic`）

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

base 11 是"通用基线"——不论项目是什么形态，这 11 类基本都会出现。当 `audit-planner` 检测项目 profile 命中具体场景时，会从下列 preset 中挑一份**针对性更强的 checklist** 替代 base 11（或并入 base 11 后做删减）。

## 2. Scenario Presets

每份 preset 是一份 `review_checklist.categories[]` 蓝本。详细 id / description / severity_default / examples 见对应文件：

| preset id | 文件 | 适用项目 |
|---|---|---|
| `generic` | （即本文档 base 11） | 未命中任何特定 architecture |
| `c-cpp-embedded` | [`scenario-presets/c-cpp-embedded.md`](scenario-presets/c-cpp-embedded.md) | 嵌入式 C/C++（baremetal / RTOS、单设备） |
| `c-cpp-embedded-soa` | [`scenario-presets/c-cpp-embedded-soa.md`](scenario-presets/c-cpp-embedded-soa.md) | 嵌入式 C/C++ + SOA（AUTOSAR / SOME/IP / DDS / 多服务通信） |
| `python-web-service` | [`scenario-presets/python-web-service.md`](scenario-presets/python-web-service.md) | Python web 服务（FastAPI / Flask / Django 等） |
| `nodejs-web-service` | [`scenario-presets/nodejs-web-service.md`](scenario-presets/nodejs-web-service.md) | Node.js 服务（Express / NestJS / Fastify） |
| `frontend-spa` | [`scenario-presets/frontend-spa.md`](scenario-presets/frontend-spa.md) | 前端 SPA（React / Vue / Svelte / Angular） |
| `cli-tool` | [`scenario-presets/cli-tool.md`](scenario-presets/cli-tool.md) | CLI 工具 / 单二进制程序 |
| `data-pipeline` | [`scenario-presets/data-pipeline.md`](scenario-presets/data-pipeline.md) | 数据 / ML pipeline（Airflow / Prefect / Spark 等） |

**冗余说明**：preset 的 category 集合通常**不是** base 11 的真子集——比如 `c-cpp-embedded-soa` 包含 `memory-safety`（base 11 没有，因 base 11 是高级语言中性的）也省略 `i18n-or-encoding`（嵌入式场景几乎用不到）。这是有意为之：场景化清单的目标是"少而准"，不是"包山包海"。

## 3. 添加自定义 preset

参考 [`scenario-presets/_template.md`](scenario-presets/_template.md)：

1. 在 `scenario-presets/` 下新建 `<preset-id>.md`
2. 顶部按 template 填写 `When to Use` + `Categories` 表
3. 每个 category 必填：`id`、`description`、`severity_default`、3 个 `examples`
4. 把 preset id 加进本文档 §2 表格
5. 可选：在 `project-profile-rubric.md` 加新的命中规则
6. 用户在 `audit-planner` Step 0.5 可用 `swap-preset <preset-id>` 切换；或在 Step 1 直接传 `--preset <preset-id>` 参数

## 4. 边界与去重规则

### 4.1 一条 finding 一个 category

不允许 `category=["correctness", "error-handling"]`。若问题在多个 category 维度都成立，按"哪个维度后果更严重"取主导。下表给的是 base 11 的二选一规则；preset 内部应在 preset 文件内自己列出对应的二选一表（如 `memory-safety vs error-handling` → `memory-safety` 优先）：

| 二选一场景（base 11） | 优先取 |
|---|---|
| security vs others | `security` |
| correctness vs typing（运行时 vs 编译时） | `correctness` |
| concurrency vs error-handling（并发触发的异常） | `concurrency` |
| resource-leak vs error-handling（异常路径漏关闭） | `resource-leak` |
| performance vs correctness | `correctness`（如果会算错） / `performance`（如果只是慢） |

### 4.2 不入分类的"问题"（不要写成 finding）

- 代码风格 / 命名 / 缩进 → 不在本 pack 范围（用 `hf-code-review` + STYLE 偏好）
- 缺测试 / 测试覆盖度 → `hf-test-review`
- 文档缺失 / 注释不全 → `hf-traceability-review`
- 架构 / 模块边界违反 → `hf-code-review` CR7 / `hf-design-review`
- "感觉以后可能要重构" → 不出 finding（reviewer 不做建议性意见）

### 4.3 category 不在 checklist 内怎么办

reviewer 扫到的疑似问题如果**没有任何 category** 能容纳，且用户已确认 checklist：

- 优先把问题改写为 checklist 内最接近的 category（在 `evidence.reasoning` 内备注"原本归属 X，因 checklist 未包含 X 暂归 Y"）
- 若实在套不进任何 checklist category 且问题严重度 ≥ medium，**暂存为本模块返回摘要中的 `skipped_findings` 提示，并建议用户在下一 run 时把 X 加入 checklist 重审**
- 不允许越权把 X 直接写进 `finding.category` 提交给 verifier（verifier 会拒收）

## 5. 相关 skill 切换

- `hf-bug-patterns`：若同一类问题在多 run 中反复出现（≥ N 次），考虑用 `hf-bug-patterns` 沉淀为可复用模式（本 pack 不直接做沉淀，只出当前 finding）

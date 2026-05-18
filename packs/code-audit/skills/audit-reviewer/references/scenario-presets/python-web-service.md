# Scenario Preset — `python-web-service`

针对 Python 后端 web 服务（FastAPI / Flask / Django / Starlette / Tornado / aiohttp）。聚焦输入校验、auth/authz、SQL、依赖、并发 / async、序列化、observability。

## When to Use

`audit-planner` 在 Step 0.5 推荐本 preset，当满足：

- 主语言 = python
- 命中 web framework（`fastapi` / `flask` / `django` / `starlette` / `tornado` / `aiohttp` in deps）
- 或顶层有 `openapi.yaml` / `Dockerfile` EXPOSE 端口

## Categories

| id | description | severity_default | examples |
|---|---|---|---|
| `input-validation` | request payload / query / header 未走 pydantic / schema 校验 / 未限长 / 未类型化 | high | `request.json["amount"]` 直接当 int 用未捕获；JSON body 上限未设 |
| `auth-authz` | 缺鉴权 / 权限检查在错误层 / JWT 验证缺 issuer/audience / 角色判断在 client 侧 | critical | `@router.get` 漏 `Depends(current_user)`；admin 接口仅靠前端隐藏；JWT 验签忽略 alg=none |
| `sql-injection` | 字符串拼 SQL / ORM raw 未参数化 / ORDER BY 注入 | critical | `db.execute(f"SELECT ... WHERE id={id}")`；Django `.extra(where=[user_input])` |
| `secrets-and-config` | 硬编码 secret / config 默认值过宽 / debug mode 进生产 / `.env` 提交仓库 | high | `SECRET_KEY = "dev-key"` 进 main；CORS `allow_origins=["*"]` + `allow_credentials=True` |
| `error-handling` | 异常吞没 / 错误返回 500 + stacktrace 暴露 / 未捕获导致 worker 崩 | medium | `except Exception: pass`；`debug=True` 在生产；async task 异常未 await 失踪 |
| `async-concurrency` | sync 阻塞调用混入 async / 共享 mutable state / event loop 错用 | high | `time.sleep(5)` 在 async handler；module-level dict 跨请求共享；`asyncio.run` 在已运行 loop 内 |
| `database` | N+1 query / 连接池漏 / 事务边界错 / 隔离级别不当 / 死锁未重试 | high | ORM lazy load 在循环；`with db.begin()` 忘 commit；唯一约束冲突未捕获 |
| `dependency-vuln` | 已知漏洞依赖 / 未 pin / latest tag 拉镜像 / 第三方 SDK 弃用 | medium | `requirements.txt` 无 `==`；`requests<2.31` 已 CVE；`urllib3<2.0` 已 EOL |
| `resource-leak` | 文件 / 连接 / socket / 后台 task 未释放 / context manager 未用 | medium | `open()` 后 early-return；`httpx.Client` 不 close；`asyncio.create_task` 引用丢失 |
| `dos` | 无 timeout / 无 size limit / 正则灾难性回溯 / 未 rate limit 关键端点 | high | `requests.get` 无 timeout；`re.match(r"(a+)+", input)`；登录无 throttle |
| `serialization` | datetime 时区错 / float 精度损失 / 自定义 encoder 漏 None / pickle 信任远端 | medium | `pickle.loads(request.body)`；datetime 不带 tz 入库；float 精度损失给金额字段 |
| `observability` | 关键路径无 log / log 包含 secret / metric 维度爆炸 / trace context 未透传 | low | login 失败仅静默；access log 把 password 印出；user_id 作为 metric label |
| `correctness` | 业务逻辑错 / off-by-one / 边界遗漏 / 货币 / 时间 / 时区算错 | high | 分页偏移错 1；UTC vs local 时区混用；Decimal vs float 混算 |
| `typing` | 类型注解错 / Optional 未守护 / mypy ignore 滥用 | low | 函数声明 `-> User` 但分支返回 `None`；`# type: ignore` 堆积 |
| `dead-code` | 不可达分支 / 未使用 endpoint / 永真分支 | low | 注释掉的 if；feature flag 永久 on/off |
| `contract-violation` | OpenAPI / pydantic schema 与实际 response 不符 / 字段大小写 / 必填漂移 | medium | OpenAPI 说 `int` 实际返回 `str`；新增字段未更新 schema |

## 二选一仲裁规则

| 二选一场景 | 优先取 |
|---|---|
| `sql-injection` vs `input-validation` | `sql-injection` |
| `auth-authz` vs `input-validation`（鉴权字段未校验） | `auth-authz` |
| `secrets-and-config` vs `dos`（默认无 timeout） | `dos` |
| `async-concurrency` vs `correctness` | `async-concurrency` 若根因在 async；否则 `correctness` |
| `dependency-vuln` vs `security` | `dependency-vuln`（更 actionable） |

## 不收 base 11 中的哪些 category

- 拆细 `security` → `auth-authz` / `sql-injection` / `dos` / `secrets-and-config`
- 拆细 `performance` → 大半归 `database` / `async-concurrency`，剩余归 `correctness`
- 拆细 `concurrency` → `async-concurrency`（web 服务以 async 为主）

## risk_focus 建议

- `auth-authz`
- `input-validation`
- `dependency-vuln`
- `dos`

## 参考资料

- OWASP Top 10
- OWASP API Security Top 10
- FastAPI security tutorial
- Django security checklist
- Bandit / pip-audit / safety

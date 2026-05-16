# Verifier Rubric

5 种 status 的详细判定标准 + 反例。

## 决策树

```
读 finding + 源码
  │
  ├─ code_snippet 与源码对不上？ ─► rejected (snippet mismatch)
  │
  ├─ reasoning 描述的触发路径在代码中不可达？ ─► rejected (unreachable claim)
  │
  ├─ 证据成立 && severity 合理？ ─► confirmed
  │
  ├─ 证据成立 && reviewer 低估 severity（如把可注入 SQL 标为 medium）？ ─► upgrade
  │
  ├─ 证据成立 && reviewer 高估 severity（如把一个 dead-code 标为 high）？ ─► downgrade
  │
  └─ 证据不全 + 不是明显误报？ ─► needs_more_evidence （限一次）
```

## 5 种 status 反例

### confirmed

✅ 好例：

```
reason: "已读 src/runtime/session_manager.py L142-148。第 143 行 self.sessions[session_id] 确无 KeyError 防护。在 archive() 第 88 行可见同 dict 在另一线程被 pop 的路径。"
evidence_check: "Read session_manager.py L88-148; grep 'self.sessions\\[' 全文 8 处匹配；read tests/runtime/test_session_manager.py 确认无并发 case。"
```

❌ 反例：

```
reason: "Looks correct."
evidence_check: "Verified."
```

→ 这种"形式确认"应被工具或 review 拦截。

### rejected

✅ 好例：

```
reason: "Reviewer 描述的 KeyError 路径不可达。源文件 L142 实际是 self.sessions.get(session_id, None)，已有 None 防护（reviewer 引用的 code_snippet 与原文件不一致，可能基于旧版本）。"
evidence_check: "Read session_manager.py L140-150 (current sha=b7e2..., finding sha=a3b2...). 文件已被修改。"
```

❌ 反例：

```
reason: "我不认为这是 bug。"
evidence_check: "Done."
```

### upgrade

✅ 好例：

```
reason: "原 severity=medium。但该 KeyError 路径在 archive() 主流程上，会导致所有归档失败，触发条件是常见的并发 archive，应升 high。"
evidence_check: "Read session_manager.py L88-148; trace archive() caller in cli.py."
severity_after: "high"
```

### downgrade

✅ 好例：

```
reason: "原 severity=high。但触发条件需要外部传入 line_end 为负数，而所有调用方都在传入前做了 max(0, ...) 防护，实际不可达。仍是 info 级别（接口约束应在 protocol 中明确）。"
evidence_check: "Read 3 caller sites in cli.py, agent.py, ingest/pipeline.py — 全部走 sanitize 路径。"
severity_after: "info"
```

### needs_more_evidence

✅ 好例：

```
reason: "Reviewer claim 在并发场景 race，但没有给出运行时旁证或同源 issue 链接。当前代码静态读不出竞态（已加锁）。要求补充：(a) 实际崩溃日志 / 复现脚本，或 (b) 锁未覆盖的代码路径具体指向。"
evidence_check: "Read session_manager.py L88-148 + L201-220 (lock acquire/release). 锁覆盖看似完整。"
```

reviewer 收到 `needs_more_evidence` 后，应：

- 补 evidence（重写 `reasoning` + `related_files`）→ verifier 再判一次（终态）
- 或撤回 finding（reviewer 自我 reject，写 `verifier.status=rejected` + reason 含 "withdrawn by reviewer after evidence request"）

## 反"橡皮图章"规则

verifier agent 在一个 run 内的 status 分布若满足下列任一条件，应触发自检：

- `confirmed` 占比 > 95% → 可能未严肃核对，重审
- `rejected` 占比 > 80% → 可能 reviewer 整体输出有结构问题，应回退到 audit-reviewer 重做
- 所有 `reason` 字段文本相似度 > 80% → 模板化复制，重审

agent 内置自检逻辑：在写 `confirmed.json` 之前 echo 一次分布统计，若触发上面规则，给出警告。

## category 不可改

verifier 不允许修改 finding 的 `category`。若认为 reviewer 分类完全错误：

- **如果分类错但问题成立**：仍 `confirmed`，但在 `reason` 备注 "category may be better as <X>，reviewer 可在下一 run 调整"
- **如果分类错且问题不成立**：`rejected`

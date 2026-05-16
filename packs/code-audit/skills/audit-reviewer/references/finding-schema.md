# Finding Schema

每条 finding 的 JSON 结构。`findings/<module>.json` 是 finding 数组（按 `line_start` 升序）。

## 完整示例

```json
{
  "id": "F-audit-2026-05-16-0435-007",
  "run_id": "audit-2026-05-16-0435",
  "module": "runtime",
  "file": "src/garage_os/runtime/session_manager.py",
  "line_start": 142,
  "line_end": 148,
  "file_sha256": "a3b2...",
  "title": "_trigger_memory_extraction 内 KeyError 未被捕获",
  "category": "error-handling",
  "severity": "high",
  "confidence": "high",
  "description": "_trigger_memory_extraction 在第 143 行直接索引 self.sessions[session_id]，若 session 已被并发 archive 删除则抛 KeyError，向上冒泡到调用方 archive() 顶层导致整个归档流程崩溃，且 F013-A SkillMiningHook 也不会触发。",
  "evidence": {
    "code_snippet": "def _trigger_memory_extraction(self, session_id: str) -> None:\n    meta = self.sessions[session_id]\n    if meta.is_archived:\n        return\n    ...",
    "reasoning": "1) 第 143 行 self.sessions[session_id] 无 KeyError 防护；2) grep self.sessions[ 模式可见同文件第 88 行 archive() 路径有可能在另一线程 pop 该 key；3) tests/runtime/test_session_manager.py 无对应并发 case，意味着该路径未被测试覆盖。",
    "trigger_conditions": "并发场景：线程 A 正在 _trigger_memory_extraction 上下文中，线程 B 已 pop session_id 后",
    "expected_vs_actual": "expected: 优雅处理 missing session 并 early-return；actual: KeyError 抛到调用栈顶，归档失败",
    "related_files": [
      "src/garage_os/runtime/session_manager.py:88",
      "tests/runtime/test_session_manager.py"
    ]
  },
  "suggested_fix": "把 self.sessions[session_id] 改为 self.sessions.get(session_id)，None 时 early-return 并 log debug；或在 archive() 持有锁直到 _trigger_memory_extraction 完成。",
  "reviewer": {
    "agent": "code-audit-reviewer-agent",
    "ts": "2026-05-16T04:35:12Z"
  },
  "verifier": {}
}
```

## 字段定义

### Top level

| 字段 | 必需 | 类型 | 由谁写 | 说明 |
|---|---|---|---|---|
| `id` | ✅ | `str` | reviewer | `F-<run_id>-<seq>`，`seq` 从 001 起，run 内全局递增 |
| `run_id` | ✅ | `str` | reviewer | 与 plan.json 一致 |
| `module` | ✅ | `str` | reviewer | 与 plan.json `modules[].name` 一致 |
| `file` | ✅ | `str` | reviewer | 相对仓库根的路径 |
| `line_start` | ✅ | `int` | reviewer | 1-indexed |
| `line_end` | ✅ | `int` | reviewer | 1-indexed，闭区间，`>= line_start` |
| `file_sha256` | ✅ | `str` | reviewer | 64 字符 hex，审查时文件内容的 sha256 |
| `title` | ✅ | `str` | reviewer | 一句话标题（≤ 80 字符） |
| `category` | ✅ | `str` enum | reviewer | 11 类之一，见 `bug-taxonomy.md` |
| `severity` | ✅ | `str` enum | reviewer | `critical` / `high` / `medium` / `low` / `info` |
| `confidence` | ✅ | `str` enum | reviewer | `high` / `medium` / `low` |
| `description` | ✅ | `str` | reviewer | 自然语言说明，2-5 句，含触发场景 + 后果 |
| `evidence` | ✅ | `object` | reviewer | 见下 |
| `suggested_fix` | ✅ | `str` | reviewer | 建议修复方式，1-3 句 |
| `reviewer` | ✅ | `object` | reviewer | `{agent, ts}` |
| `verifier` | ✅ | `object` | verifier | reviewer 占位 `{}`，verifier 写入 |

### `evidence`

| 字段 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `code_snippet` | ✅ | `str` | 原代码片段，含问题行 + 上下 2-3 行上下文 |
| `reasoning` | ✅ | `str` | 为什么这是 bug，至少 2 句话 |
| `trigger_conditions` | ✅ | `str` | 什么时候触发 |
| `expected_vs_actual` | ✅ | `str` | 期望行为 vs 实际行为 |
| `related_files` | ❌ | `array<str>` | 旁证文件路径或 `path:line` 列表 |

### `reviewer`

| 字段 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `agent` | ✅ | `str` | 通常 `code-audit-reviewer-agent` |
| `ts` | ✅ | `str` | ISO 8601 UTC |

### `verifier`（由 `audit-verifier` 填）

| 字段 | 必需 | 类型 | 说明 |
|---|---|---|---|
| `status` | ✅ | `str` enum | `confirmed` / `rejected` / `upgrade` / `downgrade` / `needs_more_evidence` |
| `reason` | ✅ | `str` | 给出该判断的理由，1-3 句 |
| `evidence_check` | ✅ | `str` | 二审实际做了哪些核对（如"读 session_manager.py L88-148；grep self.sessions["） |
| `severity_after` | ❌ | `str` enum | 仅当 status=upgrade/downgrade 时写，新的 severity 值 |
| `agent` | ✅ | `str` | 通常 `code-audit-verifier-agent` |
| `ts` | ✅ | `str` | ISO 8601 UTC |

## 不变量

1. `verifier` 在 reviewer 阶段必须以 `{}` 占位（不得缺失或 `null`），保证下游 schema 验证可断言"verifier 字段存在"
2. `id` 在一个 `run_id` 内全局唯一
3. `line_start <= line_end`，两者均 1-indexed
4. `category` / `severity` / `confidence` / `verifier.status` 必须是 enum 值之一，写错的应被 `audit-reporter` 在渲染前拒绝并报错（防止报告里出现拼写错误的 severity）

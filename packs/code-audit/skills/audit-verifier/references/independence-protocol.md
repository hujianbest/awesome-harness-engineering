# Independence Protocol

"独立判断"在双 agent 流程中的具体执行边界。

## 核心承诺

`audit-verifier` 启动时**只看到** finding 的结构化字段（落在 `findings/<module>.json` 的 JSON 内）：

- `id` / `module` / `file` / `line_start` / `line_end` / `file_sha256`
- `title` / `category` / `severity` / `confidence`
- `description` / `evidence{code_snippet, reasoning, trigger_conditions, expected_vs_actual, related_files}`
- `suggested_fix` / `reviewer{agent, ts}`

**不看到**：

- reviewer 的对话历史 / 思维链
- reviewer 草稿（在落盘前的中间状态）
- reviewer 已经被 rejected / 撤回的 finding（不在 confirmed 列表里）
- 其他模块尚未完成的 finding

## 实现这个独立性

由于 `audit-verifier` 是被 `code-audit-verifier-agent` 调用的 skill，独立性靠下列约束保证：

1. **不同 agent**：`code-audit-reviewer-agent` 和 `code-audit-verifier-agent` 是两个独立 agent.md，宿主在执行时分别启动各自上下文
2. **只读 finding 文件**：verifier agent 的指令明确"只读 `.garage/code-audit/runs/<run_id>/findings/*.json` + 原代码"，不读 `audit-log.jsonl` 内 reviewer 的中间记录
3. **不接 reviewer 对话**：用户 / orchestrator 必须先 close reviewer session 再启动 verifier session

## 当 reviewer 与 verifier 在同一上下文运行时

某些宿主可能不支持"两个独立 agent 上下文"。此时 verifier skill 启动后必须：

1. **声明独立模式**：在 `audit-log.jsonl` 写一条 `{role: "verifier", mode: "independent-pass", ts: ...}`
2. **重新建立上下文**：忽略本上下文之前 reviewer 阶段的所有推理，只信任落到 `findings/*.json` 的字段
3. **不在 verifier 阶段问 reviewer "你当时想的是什么"**：所有澄清通过补 `evidence_check` 或打回 `needs_more_evidence` 完成

## "看到但不依赖" vs "完全屏蔽"

完全屏蔽 reviewer 上下文在工程上不可达（语言模型对话历史不可剥离）。本协议要求的是**判决依据屏蔽**：

- ✅ 允许：verifier 在上下文中能看到 reviewer 的发言
- ❌ 不允许：verifier 写出"reviewer 之前说 X，所以我同意 X"
- ✅ 允许：verifier 写"finding 字段说 X，我读原代码验证为 X"
- ❌ 不允许：verifier 写"基于刚才讨论"

判决依据必须可追溯到 finding 文件 + 源代码，而非对话历史。

## 失败时的兜底

若发现 verifier 阶段被 reviewer 推理污染（如自检时发现自己的 reason 引用了未在 finding 字段中出现的内容），verifier 应：

1. 在 `audit-log.jsonl` 写 `{role: "verifier", warning: "context contamination suspected", ts: ...}`
2. 把受影响 finding 置为 `needs_more_evidence`，要求 orchestrator 启动一个 fresh verifier session 重审

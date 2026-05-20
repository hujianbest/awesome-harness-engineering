# Per-Module Context Protocol

> **核心约束**：每个模块的 `audit-reviewer` 调用都应在**独立、新鲜的对话上下文**里完成；多个模块**不要**塞在同一个对话里串跑。

本文档解释为什么、以及在每家宿主上具体怎么做。

## 1. 为什么要"按模块独立上下文"

LLM 的对话上下文有硬性 token 上限。一次 audit run 通常涉及 N 个模块，每个模块至少要把"模块内全部源文件 + checklist + finding 草稿"装进上下文。如果 N 个模块塞在同一个会话里串跑：

- **上下文堆叠**：模块 1 的代码 + 模块 1 的 finding 草稿 + 模块 2 的代码 + 模块 2 的 finding 草稿 + ……越往后总 token 越接近上限
- **触发上下文压缩 / 滑窗淘汰**：宿主或模型自动总结、丢弃前面模块的细节，剩下的"压缩摘要"已经无法支撑高保真审查
- **互相污染**：模块 1 的 finding 草稿在上下文里是"既成事实"，影响模块 2 起判 severity / category 时的锚点
- **疲劳期 false negative**：经验上 reviewer 跑到第 4-5 个模块以后，命中率明显下降——这是上下文压缩 + 注意力分散的复合症状

每模块独立上下文则恰好相反：

- 单次上下文只装一个模块的内容（典型 ≤ 12k tokens 输入），远低于硬上限
- 上下文清白：reviewer 只看 `plan.json` + 本模块源码 + checklist，不看其它模块的 finding 草稿
- 每个模块得到同等的"注意力预算"，命中率不随顺序衰减
- 中断恢复友好：即便某个模块的会话崩了，其它模块的 finding 不受任何影响

**这是一审的"独立性契约"**：与二审 verifier 在新会话独立复核的契约（`audit-verifier/references/independence-protocol.md`）形成完整闭环——一审在模块之间也要独立。

## 2. 操作模型

### 2.1 单模块工作单元（Module Work Unit, MWU）

每个 MWU 由用户在宿主里发起一个**新对话 / 新 session**，对话生命周期 = 一个模块的 finding 草稿落盘：

```text
[新对话 N]
   ↓
audit-reviewer 读 plan.json 找下一个 status=pending 的模块
   ↓
逐文件扫描该模块、出 finding
   ↓
findings/<module>.json 落盘 + plan.json status=done
   ↓
[对话 N 终结] → 用户发起对话 N+1 处理下一个模块
```

不要：

- ❌ 在同一会话里跑完 module A 后接着跑 module B
- ❌ 写"上次发现了 X，现在再看下一个模块"这类承前启后的描述
- ❌ 把多个模块 finding 写到同一个 `findings/all.json`

### 2.2 调度责任：用户 vs orchestrator

`code-audit-reviewer-agent` 现在是**外层调度**，不是"一口气跑完"的 worker。它应：

1. 在第一次调起时跑完 audit-planner Step 0/0.5/1-4，把 plan.json 落定
2. 每次只挑一个 `status=pending` 的模块（按 priority desc + path asc），调一次 `audit-reviewer`
3. 该模块完成后**立即返回控制权 + 移交消息**，告诉用户在新对话里继续下一个模块
4. 不进入循环、不在同一会话里继续抓下一个模块

非交互场景（CI / 脚本，`--yes` + `--auto-loop`）才允许同 session 串跑，且必须在 `audit-log.jsonl` 里写一条 warning：`{role: "reviewer", warning: "auto-loop mode: per-module independence relaxed", ts: ...}`，并在最终摘要里告知用户。

## 3. 三家宿主的具体做法

### 3.1 OpenCode

OpenCode 内每开一个新会话即产生独立 context。建议每模块流程：

```text
# 对话 1 — 初始化 plan
You: 请用 code-audit-reviewer-agent 审查 src/garage_os/runtime/
Agent: [audit-planner] ... plan.json 落盘，5 个模块，下面处理 priority=high 的 module=runtime:state-machine
       [audit-reviewer module=runtime:state-machine] ... findings/runtime__state-machine.json 落盘
       下一步请【新开对话】继续：
         "请用 code-audit-reviewer-agent --resume run audit-2026-05-20-0935 处理下一个模块"

# 对话 2（新建）
You: 请用 code-audit-reviewer-agent --resume run audit-2026-05-20-0935 处理下一个模块
Agent: [audit-reviewer module=runtime:session-manager] ... 落盘 ...
       请新对话继续 ...
```

直到所有模块 status=done 后，agent 返回"一审完成 → 启动 verifier"的最终移交。

### 3.2 Claude Code

Claude Code 同样支持 `/clear` 或新 conversation 来清空上下文：

```text
# 主对话
You: 请用 code-audit-reviewer-agent 审查 src/
Agent: ... module=runtime 完成；请清空上下文 (/clear) 或开新对话再说 "--resume <run-id>" 继续

You: /clear
You: 请用 code-audit-reviewer-agent --resume run audit-2026-05-20-0935 处理下一个模块
Agent: ... 处理 module=knowledge ...
```

`/clear` 等价于新 conversation——subagent 也会重新加载，符合独立上下文要求。

### 3.3 Cursor

Cursor 没有 agent surface，必须手动按 skill 唤起，但**每模块开新对话**这一约束依然适用：

```text
# 对话 1
You: 请使用 audit-planner skill 切分 src/garage_os/ 的模块
（plan.json 落盘）

# 对话 2 — 新对话
You: 请使用 audit-reviewer skill 处理 run audit-2026-05-20-0935 的下一个 pending 模块

# 对话 3 — 新对话
You: 请使用 audit-reviewer skill 处理 run audit-2026-05-20-0935 的下一个 pending 模块
（重复直到所有模块 done）
```

## 4. 模块越大越要拆——budgets 收紧

为了让单个模块塞得下"一个新会话的上下文"，`audit-planner` 0.3.0 起把默认预算从 token=30000 / files=20 收紧到 token=12000 / files=8。原因：

- 12k 输入 token + 输出 finding ≈ 单次 round-trip 不超过 25k，远低于主流模型 200k 上限——给注意力留富余
- 8 文件覆盖大多数原子模块（一个 service / 一个 router 文件 + helpers）
- 超出预算的目录强制走"深度目录树切分"（见 `module-partition-rubric.md` 策略 4），按二级 / 三级子目录再切

如果你确实想审一个超大单文件（> 800 LoC），audit-planner 仍允许（不切单文件），但会在 `module.notes` 写 `oversized-single-file: review may suffer accuracy loss; consider refactoring before audit`。

## 5. 失败兜底

万一你不小心在同一会话里串跑了多个模块：

- 不要重写历史。继续把当前 run 跑完
- 在 `audit-log.jsonl` 里追加 `{role: "reviewer", warning: "per-module-context violated; manual recovery", run_id: ..., ts: ...}`
- 强烈建议**重跑该 run 的 verifier 阶段**（verifier 启新会话 + 独立读 finding 字段，可以部分纠偏一审的污染）
- 下次开始新 run 时严格遵守"每模块新对话"

## 6. 与 verifier independence-protocol 的关系

`audit-verifier/references/independence-protocol.md` 守护**reviewer ↔ verifier 之间**的独立。本文档守护**reviewer 内部模块 ↔ 模块**的独立。两者一起构成"上下文不污染"的完整边界：

```
[reviewer module=A 新会话]  ──┐
[reviewer module=B 新会话]  ──┼── 一审独立分散                 (本协议)
[reviewer module=C 新会话]  ──┘
                              │
                              ▼
[verifier 新会话]           ──── 二审独立复核                  (independence-protocol.md)
                              │
                              ▼
[reporter] ───────────────── 渲染（不需要新会话；纯计算）
```

## 7. Verification

reviewer agent / orchestrator 在每个 MWU 末尾自检：

- [ ] 本会话内只调了 audit-reviewer 一次（针对单一模块）
- [ ] `plan.json` 中正好一个模块从 `pending` 变 `done`
- [ ] 移交消息明确指引用户开新会话 + 给出 `--resume` 指令
- [ ] `audit-log.jsonl` 末尾不含同一 run、同一会话内多个 module 的 `module_done` 事件（除非显式 auto-loop 模式）

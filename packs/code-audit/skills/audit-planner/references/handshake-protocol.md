# Handshake Protocol — Step 0.5 必读

`audit-planner` Step 0.5 的握手契约。本文档专门治"LLM 把握手当文档读、不真停下"这一类常见错误。

## 1. 为什么要有这份协议

v0.2.0 把"项目识别 + checklist 与用户确认"加进 audit-planner。但实测发现：LLM 经常**把 checklist 打印出来后**继续在同一条回复里调 audit-planner 的切模块 step、调 audit-reviewer 扫模块——用户根本来不及说"ok"或"我想调整"。

结果：

- 用户在对话里被迫看着一堆模块扫描结果，明明检视清单根本没和他对齐
- `plan.json` 里 `user_confirmed=true` 写错了（user 没有 confirm 过）
- 整个 v0.2.0 引入的"针对性 review_checklist"机制白做了

本文档说明**怎么做才算真的握手**，以及**LLM 在自检时应该问哪些问题**。

## 2. 握手最小单元 = 两次消息往返

握手 = 两条独立的 LLM 回复 + 中间用户回 1 条消息。

```
[turn N-1]  user:  "审查 src/ 看有没有 bug"
[turn N  ]  agent: 输出 profile + draft checklist + "=== ⏸️ 等待确认 ===" 段
                  ← 这条消息结束, agent 不再调任何 tool, 不再继续 thinking out loud
[turn N+1]  user:  "ok" (或 "del 13,14" / "swap-preset python-web-service" / ...)
[turn N+2]  agent: 处理用户回复 → 若 ok 则进入切模块, 若是修改类指令则回到 turn N 重新回显
```

**最小情况下整个握手占用 2 个 agent 回合**（turn N 显示, turn N+2 处理 ok 后进入切模块）。

**如果用户做了修改**：每次修改 = 多一个回合往返，最终 user 回 `ok` 才结束握手。

## 3. 严格回显模板（turn N 必须长这样）

```
=== Detected Project Profile ===
languages:      <c, cpp>
architectures:  <embedded, soa>
frameworks:     <FreeRTOS, AUTOSAR-Classic, SOME/IP>
risk_focus:     <memory-safety, isr-safety, ipc-contract, real-time>
signals:
  - <src/board/stm32f4xx_hal_conf.h>
  - <ipc/proto/*.arxml (12 service contracts)>
  - <linker script bsp/STM32F407.ld>

=== Suggested Review Checklist (preset: <c-cpp-embedded-soa>) ===
 1. <memory-safety>        — <UAF / double-free / 缓冲区溢出 / OOB / dangling pointer>
 2. <undefined-behavior>   — <signed overflow / strict aliasing / 对齐 / NULL deref>
 3. <isr-safety>           — <ISR 内阻塞调用 / 非 reentrant API / 缺 volatile / 优先级反转>
 ... (列全部 categories, 不要省略, 不要写 "..." 让用户去猜)
N. <coding-standard>       — <MISRA-C / CERT-C 高风险条款>

=== ⏸️ 等待确认 ===
请回复以下任一指令再继续:
- ok                                — 接受当前 checklist, 开始切模块 + 扫描
- del N1,N2,...                     — 删除某几条（按序号）
- add <id>:<description>            — 新增自定义类别
- swap-preset <preset-name>         — 切换 preset (可选: c-cpp-embedded-soa, c-cpp-embedded, python-web-service, frontend-spa, generic)
- edit N <new description>          — 改某条描述
- skip handshake                    — 强制跳过握手, 直接用当前 checklist
```

要点：

1. 必须包含 `=== ⏸️ 等待确认 ===` 这一段（带 emoji），它是 STOP 信号的视觉标记
2. categories 必须**全部列出**——不要写 "... (共 15 条)" 让用户去猜
3. 接受指令清单也要全列——这是给用户的菜单，省略会让用户猜
4. 这一条消息结束后**不要再多说一句话**：不要"我现在去切模块了"，不要"如果你同意 ok 我就开始扫"——这些都是在描述未来动作，但 LLM 经常把"描述"和"执行"混在一起，最稳的是只显示模板然后停

## 4. GOOD vs BAD 例子

### ✅ GOOD example

**turn N-1** (user):

> 帮我审查 `src/` 看有没有 bug

**turn N** (agent, **一条消息内**):

```
=== Detected Project Profile ===
languages:      c, cpp
architectures:  embedded, soa
frameworks:     FreeRTOS, AUTOSAR-Classic, SOME/IP
risk_focus:     memory-safety, isr-safety, ipc-contract, real-time
signals:
  - src/board/stm32f4xx_hal_conf.h
  - ipc/proto/*.arxml (12 service contracts)
  - linker script bsp/STM32F407.ld

=== Suggested Review Checklist (preset: c-cpp-embedded-soa) ===
 1. memory-safety        — UAF / double-free / 缓冲区溢出 / OOB / dangling pointer
 2. undefined-behavior   — signed overflow / strict aliasing / 对齐 / NULL deref
 3. isr-safety           — ISR 内阻塞调用 / 非 reentrant API / 缺 volatile / 优先级反转
 4. concurrency          — RTOS 任务间共享状态无锁 / 双锁顺序 / 信号量错用
 5. real-time            — 时序超 deadline / 看门狗未喂 / 长循环阻塞调度
 6. resource-management  — 堆未释放 / mutex/semaphore 未归还 / 句柄泄露 / 初始化顺序错
 7. error-handling       — 返回值未检 / errno 未处理 / 异常路径吞错
 8. ipc-contract         — SOA IDL 字段不匹配 / 版本兼容 / 序列化端序
 9. hardware-resource    — 寄存器访问顺序 / DMA / cache 一致性 / 时钟门控错配
10. security             — 外部输入未做长度/边界校验 / 弱密钥 / TOCTOU
11. portability          — endianness / sizeof / packed struct ABI
12. build-and-config     — 编译宏 / 链接顺序 / FPU/MPU 选项与硬件不符
13. dead-code            — 不可达分支 / 仅 debug 路径误入 release
14. contract-violation   — header 与 impl 漂移 / AUTOSAR/RTE 契约不符
15. coding-standard      — MISRA-C / CERT-C / AUTOSAR C++14 严重违反

=== ⏸️ 等待确认 ===
请回复以下任一指令再继续:
- ok                                — 接受当前 checklist, 开始切模块 + 扫描
- del N1,N2,...                     — 删除某几条（按序号）
- add <id>:<description>            — 新增自定义类别
- swap-preset <preset-name>         — 切换 preset
- edit N <new description>          — 改某条描述
- skip handshake                    — 强制跳过握手, 直接用当前 checklist
```

**← 这条回复到这里就结束。没有继续调 audit-planner 切模块, 没有继续调 audit-reviewer。**

**turn N+1** (user):

> ok

**turn N+2** (agent):

> 收到, checklist 已确认 (15 类, preset=c-cpp-embedded-soa). 接下来调 audit-planner 切模块...
> [然后才开始调 audit-planner Step 1-4, 写 plan.json, 等等]

---

### ❌ BAD example #1 — "打印后继续走"

**turn N-1** (user):

> 帮我审查 `src/`

**turn N** (agent, **一条消息内**):

```
=== Detected Project Profile ===
languages: c, cpp
architectures: embedded, soa
...

=== Suggested Review Checklist (preset: c-cpp-embedded-soa) ===
 1. memory-safety ...
 ... (列了 15 类)

=== ⏸️ 等待确认 ===
请回复 ok / del / add / swap-preset / edit

如果你接受默认, 我现在开始切模块.   ← ❌ 错: 这句话暗示要继续了
```

```python
[tool_call: audit-planner Step 1-4 切模块]   ← ❌ 错: 用户根本没回 ok
[tool_call: audit-reviewer 扫 module=runtime]   ← ❌ 更错
```

**结果**：用户来不及回话，模块扫描已经在跑。这就是 v0.2.0 的实测 bug。

---

### ❌ BAD example #2 — "用户描述了项目 = 同意了 checklist"

**turn N-1** (user):

> 项目是 C/C++ 嵌入式 SOA, 审一下 src/

**turn N** (agent):

```python
[tool_call: audit-planner Step 0 (推断 profile)]
[tool_call: audit-planner Step 1-4 切模块, 写 plan.json with user_confirmed=true]   ← ❌ 错
[tool_call: audit-reviewer 扫 module=rtos]
```

> 用户提到了 c-cpp-embedded-soa, 所以我选了这个 preset, 已经开始扫了...

**为什么错**：用户描述项目类型是**给 profile 检测的提示**，**不是**同意 checklist 内容。preset 里可能有用户**不**想审的类（如 `coding-standard`），用户必须看到完整 checklist 才能反馈。

---

### ❌ BAD example #3 — "我是 agent 所以我可以 --yes"

**turn N-1** (user):

> 用 code-audit-reviewer-agent 审 src/

**turn N** (agent 内部 reasoning):

> 用户调用我这个 agent, 说明他在 batch 模式, 我应该走 --yes 路径跳过 prompts.

```python
[tool_call: audit-planner Step 1-4 (skipped 握手, user_confirmed=false)]
[tool_call: audit-reviewer ...]
```

**为什么错**：调用 agent ≠ 同意跳过握手。agent 本身没有代用户同意的权限。**bypass 只能由用户在原始请求里显式写关键词触发**（详见 §5）。

---

### ✅ GOOD example #4 — 用户用 swap-preset 改了 preset

**turn N** (agent): 输出 c-cpp-embedded-soa preset → STOP

**turn N+1** (user):

> swap-preset python-web-service

**turn N+2** (agent, **一条消息内**):

```
=== Detected Project Profile ===
languages: c, cpp   ⚠ 注意 profile 检测到的是 c/cpp, 但你切到了 python-web-service preset.
                    如果项目实际是 c/cpp 嵌入式, 用 python-web-service preset 会漏掉关键 category.
architectures: embedded, soa
...

=== Suggested Review Checklist (preset: python-web-service) ===
 1. input-validation ...
 ... (列出 python-web-service 的 categories)

=== ⏸️ 等待确认 ===
请回复 ok / del / add / swap-preset / edit / skip handshake
```

**← 再次停下等用户回复**

**turn N+3** (user):

> 我知道, 项目里 c/cpp 是底层, 但实际审查目标是上层 python 服务. ok

**turn N+4** (agent): 落 plan.json + 开始切模块。

---

### ❌ BAD example #5 — 用户没意会, agent 自己开始了

**turn N** (agent): 输出 checklist → STOP

**turn N+1** (user):

> 这些类别看起来挺全的

**turn N+2** (agent):

```python
[tool_call: audit-planner Step 1-4 (作 user_confirmed=true)]
```

> 好的, 我开始切模块了 ...

**为什么错**：用户没有回 `ok`，只是评价了一句。agent 应该追问"那我开始？请回 ok 确认"，**而不是**自己揣摩用户意图。

---

## 5. Bypass 的"显式同意"清单（仅限用户原始请求出现）

只有当用户在 **本轮原始请求** 里**显式**包含下列任一关键词，才允许跳过 Step 0.5.c 的 STOP（仍把 `user_confirmed=false` 写盘并在摘要里加 ⚠）：

- `--yes` / `-y` / `assume_yes`
- `跳过确认` / `跳过握手` / `skip handshake` / `auto-yes`
- `直接开始` 同时附带了具体 preset id（如"直接用 c-cpp-embedded-soa 开始"）

**不算 bypass 的请求**（必须握手）：

- "审查 X 模块" / "扫一遍 src/"
- "项目是 C/C++ 嵌入式 SOA, 审 src/"（描述项目 ≠ 同意 checklist）
- "用 code-audit-reviewer-agent 审" / "用 agent 跑一下"（调用 agent ≠ bypass）
- "快点开始" / "尽快" / "马上"（语气词不是关键词）

## 6. Self-check（agent 每条回复结束前问自己一遍）

按下表逐条核查，任一条命中 ❌ 都意味着**握手出问题了**，要立即纠正（截断回复、把数据回滚到落 plan.json 之前、重新走 Step 0.5）：

| 自检问题 | 应该的答案 |
|---|---|
| 这一条回复里有没有 `=== ⏸️ 等待确认 ===` 段？ | 第一次显示 checklist 时：✅ 有；用户回 ok 后：可以没有 |
| 有 `=== ⏸️ 等待确认 ===` 段时, 我后面是不是又继续描述/调用了"切模块" / "audit-reviewer" / 任何写 plan.json modules 段的工具？ | ❌ 不行, 必须停 |
| 用户原始请求里有没有 §5 列出的 bypass 关键词？ | 有 → 可以跳过 STOP；没有 → 必须 STOP |
| 我有没有 把"用户描述了项目"误解成"用户同意了 checklist"？ | ❌ 没有, 这两者不同 |
| `plan.json` 的 `user_confirmed=true` 是否**只**在用户实际回了 `ok` / `确认` / `yes` 等之后才写？ | ✅ 只在那种情况写 true, 其它写 false |
| 上一次握手过的 run 不算这次握手 → 这次新 run 需要重新走 Step 0.5 吗？ | ✅ 是的, 每个 run 独立握手（resume 例外, 见 agent.md "Resume 协议"） |

## 7. 兜底：reviewer 端的二次闸门

即使 planner 因为 LLM 的判断失误漏跳了握手（写了 `user_confirmed=false`），下游 `audit-reviewer` SKILL.md 还有一层闸门：

- reviewer 加载 plan.json 时，若 `review_checklist.user_confirmed=false` 或 `review_checklist` 字段缺失，**halt** 并向用户输出"checklist 未握手, 是否确认 / 调整 / restart-planner?"
- 用户回 `confirm` / `edit ...` / `restart-planner` 之后 reviewer 才进入扫描

详见 `audit-reviewer/SKILL.md` 的 "Handshake Re-Gate" 段。

## 8. 结论

握手的实质是：**LLM 必须真的让出控制权**，让人类用户在新一轮消息里输入指令，而不是 LLM 自己脑补用户会怎么回。本协议的 §3 模板 + §6 self-check + §7 兜底，三者共同保证了用户对 checklist 的最终决定权。

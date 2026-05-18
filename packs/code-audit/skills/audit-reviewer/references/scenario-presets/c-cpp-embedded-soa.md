# Scenario Preset — `c-cpp-embedded-soa`

针对 **C / C++ 嵌入式 SOA 软件架构** 的 review checklist。典型项目：

- 域控 / 域服务器：硬件 + RTOS（FreeRTOS / Zephyr / AUTOSAR Classic / AUTOSAR Adaptive）
- 服务化中间件：SOME/IP、DDS、Zenoh、CommonAPI、CycloneDDS、Vortex
- 多 ECU / 多核 / 多任务，强调跨服务通信契约 + 实时性 + 资源安全

本 preset 既覆盖**嵌入式底层风险**（内存安全、UB、ISR、实时性），又覆盖**SOA 通信风险**（IDL 契约、序列化、版本兼容）。

## When to Use

`audit-planner` 在 Step 0.5 推荐本 preset，当满足**两项**：

- 命中"embedded"（FreeRTOSConfig.h / `*.ld` / CMSIS / STM32HAL / Zephyr / AUTOSAR build artifacts）
- 命中"soa"（`*.arxml` 服务接口 / `*.proto` / `*.fidl` / SOME/IP / DDS / Zenoh）

若仅嵌入式（无服务化）→ 用 [`c-cpp-embedded.md`](c-cpp-embedded.md)。

## Categories

| id | description | severity_default | examples |
|---|---|---|---|
| `memory-safety` | UAF / double-free / 堆栈溢出 / OOB read & write / dangling pointer / uninitialized read / 越界 memcpy | high | `free(p); ...; *p = 0;`（UAF）；`char buf[8]; strcpy(buf, user_input);`（栈溢出）；DMA 缓冲区被 cache 行盲读盲写 |
| `undefined-behavior` | signed int overflow / strict aliasing / type punning / 对齐错读 / NULL deref / shift > width / 越界数组下标 | high | `int x = INT_MAX; x++;`；`*(uint32_t*)byte_ptr` 无对齐；`(1 << 32)`；负值左移 |
| `isr-safety` | ISR 内部阻塞调用 / 非 reentrant 库 / 缺 `volatile` / 优先级反转 / 共享数据无 critical section | critical | ISR 调 `printf` / `malloc`；中断与任务共享 flag 未声明 volatile；高优先级 ISR 抢占持锁低优先级任务 |
| `concurrency` | RTOS 任务间共享状态无 mutex/sema / 双锁死锁 / 信号量 give/take 不匹配 / 跨核竞态 | high | 两任务读写全局结构体未加锁；MutexA→MutexB vs MutexB→MutexA；ISR 中 `xSemaphoreGive` 用了非 FromISR 版本 |
| `real-time` | 时序超 deadline / 长循环阻塞调度 / 看门狗未喂 / 周期任务被低优先级阻塞 / `vTaskDelay` 在硬实时路径 | high | 100 Hz 控制循环内做 flash 写；watchdog 喂狗位于可被阻塞分支；soft IRQ 处理耗时 > 1 ms |
| `resource-management` | 堆未释放 / mutex/sema 未归还 / 文件 / socket / DMA 通道句柄泄漏 / init 与 deinit 顺序错 | high | early-return 漏 `vSemaphoreDelete`；硬件外设 init 顺序倒置导致时钟门控错；环形缓冲池满后 silently overwrite |
| `error-handling` | 返回值未检 / errno 未处理 / 异常路径吞错 / RTOS API 错误码忽略 | medium | `xQueueSend(...);` 未判返回值；`HAL_xxx(...)` 返回 ERROR 后继续执行；`malloc` 后未判 NULL |
| `ipc-contract` | SOA IDL / proto / arxml 字段不匹配 / 版本兼容 / 必填字段缺失 / enum 越界 / optional 与默认值语义混淆 | critical | Provider 端 method signature 与 Consumer 端 arxml 不一致；新增字段未走 forward-compat 路径；service version major 提升未通知 |
| `serialization` | 端序 / 字节填充 / packed struct 与协议结构不符 / 数值溢出 / 字符串结尾 \0 处理 | high | 大端总线发小端裸结构；`__attribute__((packed))` 缺失导致对齐误差；CAN payload 字段位偏移错；MQTT topic UTF-8 截断 |
| `hardware-resource` | 寄存器访问顺序错 / DMA 与 cache 一致性 / 时钟门控 / GPIO 复用配置错 / 外设 init 在时钟开之前 | high | DMA 写完未做 `SCB_CleanDCache_by_Addr`；外设访问前未 enable bus clock；GPIO mode 与 AF 配置交错 |
| `security` | 外部输入未做长度 / 边界 / 类型校验 / 弱密钥 / 固定密钥 / TOCTOU / Secure boot 绕过 | high | RX 缓冲区拷贝信任远端 length 字段；AES key 写死在固件；OTA 镜像签名校验在 flash 写入后做 |
| `portability` | endianness 假设 / `sizeof(int)` 假设 / packed struct ABI / `char` 默认符号 / 64-bit 对齐 | medium | `*((uint32_t*)p)` 跨架构不同行为；`enum` 大小依赖编译器；位段顺序依赖编译器 |
| `build-and-config` | 编译宏配置错 / 链接顺序 / FPU/MPU 选项与硬件不符 / weak symbol 错绑 / debug 配置进 release | high | `-mfpu=soft` 但代码使用 float；`__weak` 被错误覆盖；release build 未关 `assert` 触发崩溃恢复路径 |
| `dead-code` | 不可达分支 / 仅 debug 路径误入 release / 永真 / 永假 condition / 残留 TODO | low | `if (0) { ... }`；`#ifdef DEBUG` 内代码因宏拼写错被 release 编入；switch default 永远到不了 |
| `contract-violation` | header 与 impl 漂移 / AUTOSAR RTE 契约不符 / 函数签名与 IDL 不一致 / 类型大小与 protocol 文档不符 | high | RTE_Call_X_Y signature mismatch；`.h` 声明 `uint32_t` 但 `.c` 实现按 `uint16_t` 处理 |
| `coding-standard` | MISRA-C / CERT-C / AUTOSAR C++14 严重违反（仅高风险条款；非全 MISRA 扫描） | medium | MISRA 17.7 函数返回值未使用（已含 error-handling 但偶有未覆盖）；CERT INT30-C unsigned wrap；MISRA 11.3 强转破坏对齐 |

## 二选一仲裁规则（preset 内部）

| 二选一场景 | 优先取 | 理由 |
|---|---|---|
| `memory-safety` vs `error-handling`（malloc 返回 NULL 后再写） | `memory-safety` | 后果更直接，崩溃风险高 |
| `memory-safety` vs `undefined-behavior`（OOB 也是 UB） | `memory-safety` | 修复 actionable 更明确 |
| `isr-safety` vs `concurrency` | `isr-safety` | ISR 路径修复更紧迫 |
| `isr-safety` vs `real-time` | `isr-safety` | ISR 内阻塞既是 ISR 安全也是实时性问题，但 ISR 维度更窄、修复方法更清晰 |
| `ipc-contract` vs `serialization` | `ipc-contract`（若 schema 不匹配）/ `serialization`（若仅字节布局错） | 按出错的层次取 |
| `hardware-resource` vs `concurrency`（DMA 与任务竞争同一缓冲） | `hardware-resource` | 硬件机制 + cache 维度优先 |
| `coding-standard` vs 其它任何 | 其它任何 | coding-standard 仅作为"无更精确 category 时的兜底"，避免变成 MISRA 全扫 |

## 不收 base 11 中的哪些 category

- **`i18n-or-encoding`**：嵌入式场景几乎不涉及多语言 / locale；字符串编码错归 `serialization` 或 `security`
- **`typing`**：C 无 type system 强约束；类型问题归 `undefined-behavior` 或 `portability`
- **`performance`**：嵌入式性能等价于"实时性 + 资源占用"，已被 `real-time` + `resource-management` 覆盖；纯算法慢的问题归 `correctness`
- **`api-misuse`**：本 preset 拆细为 `isr-safety`（RTOS API 滥用）+ `hardware-resource`（HAL/CMSIS 错用）+ `error-handling`（返回值忽略），不再用 `api-misuse` 笼统类

## risk_focus 建议

`audit-planner` 在 `profile.risk_focus[]` 默认追加：

- `memory-safety`
- `isr-safety`
- `real-time`
- `ipc-contract`

## 参考资料

- MISRA C:2012 + Amendment 2 (rule 1-22 高风险子集)
- CERT C Secure Coding Standard (INT / MEM / FIO / CON 模块)
- AUTOSAR C++14 Coding Guidelines（A-rules 重点）
- AUTOSAR Classic Platform — RTE Generator + AppHeader 契约
- AUTOSAR Adaptive Platform — ARA::COM Service Contract
- The Power of 10 Rules (Holzmann / JPL Mission Critical Code)
- Zephyr Project Coding Guidelines + Coccinelle scripts
- ARM Cortex-M Memory Barrier + Cache Maintenance ARM-DAI0321A

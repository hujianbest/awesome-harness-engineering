# Scenario Preset — `c-cpp-embedded`

针对**单设备 / 非服务化** C/C++ 嵌入式项目。本 preset 是 [`c-cpp-embedded-soa`](c-cpp-embedded-soa.md) 的子集——去掉 SOA 相关的 `ipc-contract` / `serialization` 两类。

## When to Use

`audit-planner` 在 Step 0.5 推荐本 preset，当满足：

- 命中 "embedded"（FreeRTOSConfig.h / `*.ld` / CMSIS / STM32HAL / Zephyr / Kconfig）
- **不**命中 "soa"（无 `*.arxml` / `*.proto` / `*.fidl` / SOME/IP / DDS 关键字）

若同时有 SOA → 用 [`c-cpp-embedded-soa.md`](c-cpp-embedded-soa.md)。

## Categories

引用 `c-cpp-embedded-soa.md` 同名定义。本 preset 启用：

- `memory-safety`（severity_default: high）
- `undefined-behavior`（high）
- `isr-safety`（critical）
- `concurrency`（high）
- `real-time`（high）
- `resource-management`（high）
- `error-handling`（medium）
- `hardware-resource`（high）
- `security`（high）
- `portability`（medium）
- `build-and-config`（high）
- `dead-code`（low）
- `contract-violation`（high）
- `coding-standard`（medium）

**不启用**（vs `c-cpp-embedded-soa`）：

- `ipc-contract`（无跨服务通信）
- `serialization`（若仅本地存储，纳入 `correctness` 或 `portability`）

如果该项目有跨设备但非 SOA 通信（如 CAN / SPI / I²C 协议帧），可手动 `add ipc-contract:bus-protocol field mismatch...` 把这一类加回来。

## 二选一仲裁规则

同 `c-cpp-embedded-soa.md`。

## risk_focus 建议

`audit-planner` 在 `profile.risk_focus[]` 默认追加：

- `memory-safety`
- `isr-safety`
- `real-time`
- `hardware-resource`

## 参考资料

同 `c-cpp-embedded-soa.md`（去掉 AUTOSAR 服务化部分）。

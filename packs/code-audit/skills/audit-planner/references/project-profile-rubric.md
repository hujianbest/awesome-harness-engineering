# Project Profile Detection Rubric

`audit-planner` 在 Step 0 用本 rubric 识别项目 profile（语言 + 架构 + framework + risk_focus），用来挑选 Step 0.5 的 review_checklist preset。

**底层原则**：不分析业务逻辑、不打开大量源码，仅看 metadata + 少量代表性的 build / IDL / 入口文件。检测结果**只是 draft**，必须经 Step 0.5 用户确认后才落 plan.json。

## 1. 语言识别

### 1.1 扩展名直方图

按下列扩展名扫一遍 target 目录（忽略 `tests/` / `docs/` / `build/` / `node_modules/` / `.venv/`），取文件数前 3 的语言：

| 扩展名 | 语言 |
|---|---|
| `.c .h` | c |
| `.cpp .cc .cxx .hpp .hh .hxx` | cpp |
| `.py` | python |
| `.ts .tsx` | typescript |
| `.js .jsx .mjs .cjs` | javascript |
| `.go` | go |
| `.rs` | rust |
| `.java` | java |
| `.kt .kts` | kotlin |
| `.swift` | swift |
| `.rb` | ruby |
| `.cs` | csharp |
| `.scala` | scala |
| `.dart` | dart |
| `.lua` | lua |
| `.sh .bash` | shell |

C + cpp 同时存在时按文件数比 ≥ 1.5 取主导，比例接近时 `["c", "cpp"]` 并列。

### 1.2 manifest 文件辅助

| 文件 | 推断 |
|---|---|
| `pyproject.toml` / `setup.py` / `requirements.txt` | python |
| `package.json` | typescript / javascript（看 deps 中是否含 `typescript`） |
| `Cargo.toml` | rust |
| `go.mod` | go |
| `CMakeLists.txt` / `Makefile` | c / cpp（看 src 扩展名再决定） |
| `build.gradle` / `pom.xml` | java / kotlin |
| `Gemfile` | ruby |
| `*.csproj` / `*.sln` | csharp |
| `Package.swift` | swift |

manifest 与扩展名冲突时（如 `pyproject.toml` 存在但 `*.c` 文件 90%）→ 取扩展名主导，但在 `risk_focus` 中加 `mixed-language-stack`。

## 2. 架构形态识别

### 2.1 Embedded（嵌入式）

命中**任意 ≥ 1 条**：

- `*.ld`（GNU linker script）
- `*.s` 或 `*.S`（汇编启动文件，且位于 `boot/` / `startup/` / `arch/` 路径下）
- `*.dts` / `*.dtsi`（Device Tree）
- `FreeRTOSConfig.h` / `freertos.h`
- `cmsis*.h` / `core_*.h`（CMSIS）
- `HAL_*.h` 或 `*_hal_conf.h`（STM32 HAL / Cube）
- `nrfx_*.h` / `nrf_*.h`（Nordic）
- `esp_*.h` 且 `idf_component.yml` 存在（ESP-IDF）
- `Zephyr` / `zephyr/` 顶层目录
- `Kconfig` + 顶层 `west.yml`（Zephyr / Nordic 工程）
- `picolibc` / `newlib` 依赖
- CMakeLists.txt 含 `arm-none-eabi-gcc` 或 toolchain 文件路径含 `cortex`

frameworks 字段填命中清单（如 `FreeRTOS, CMSIS, STM32HAL`）。risk_focus 默认加 `memory-safety, isr-safety, real-time, hardware-resource`。

### 2.2 SOA（service-oriented / 服务化通信）

命中**任意 ≥ 1 条**：

- IDL / proto 文件：`*.idl` / `*.proto` / `*.fidl` / `*.capnp` / `*.thrift`
- AUTOSAR：`*.arxml`（especially `*ServiceInterface*.arxml`）
- ROS / ROS2：`package.xml` + `msg/*.msg` + `srv/*.srv`
- DDS / Zenoh / SOME/IP / Cyclone DDS 关键字（`#include <dds/`、`zenoh.h`、`vsomeip` import）
- gRPC：proto + `*.pb.cc` / `*.pb.h` 生成产物
- service registry / mesh：consul / envoy / linkerd 配置文件
- microservices monorepo：`services/<name>/` 多个子目录各带独立 `Dockerfile`

frameworks 字段填命中清单（如 `AUTOSAR-Classic, SOME/IP, DDS`）。risk_focus 默认加 `ipc-contract, serialization, compatibility`。

### 2.3 Web Service

命中**任意 ≥ 1 条**：

- Python：`fastapi` / `flask` / `django` / `starlette` / `tornado` in deps
- Node：`express` / `koa` / `fastify` / `nestjs` / `hapi` in deps
- Go：`net/http` + `gin` / `echo` / `chi`
- Java：`spring-boot` in deps
- 顶层有 `openapi.yaml` / `openapi.json` / `swagger.json`
- 顶层有 `Dockerfile` 且 EXPOSE 端口 + manifest 含 HTTP framework

risk_focus 默认加 `input-validation, auth-authz, sql-injection, dependency-vuln`。

### 2.4 Frontend SPA

命中**任意 ≥ 1 条**：

- `package.json` deps 含 `react` / `vue` / `svelte` / `@angular/core` / `solid-js` / `preact`
- 顶层 `index.html` + 框架启动文件（`main.tsx` / `App.vue` / `App.svelte`）
- bundler 配置：`vite.config.*` / `webpack.config.*` / `rollup.config.*` / `next.config.*` / `nuxt.config.*` / `astro.config.*`

risk_focus 默认加 `xss, state-management, dependency-vuln, accessibility`。

### 2.5 CLI 工具 / Library

命中**任意 ≥ 1 条**：

- `pyproject.toml` 含 `[project.scripts]` 段
- `Cargo.toml` 含 `[[bin]]` 段
- `package.json` 含 `"bin": {...}`
- Go：`cmd/<name>/main.go` 结构

risk_focus 默认加 `argument-parsing, exit-code, env-var-handling`。

### 2.6 数据 / ML Pipeline

命中**任意 ≥ 1 条**：

- Python deps 含 `pandas` / `numpy` / `polars` / `dask` / `pyspark` / `airflow` / `prefect` / `dagster` / `kedro`
- Jupyter notebook (`*.ipynb`) 数量 ≥ 5
- DAG / pipeline 配置：`dags/` 目录、`pipelines/` 目录

risk_focus 默认加 `data-validation, schema-evolution, idempotency, observability`。

### 2.7 通用 / 未命中

以上都不命中时 architectures 取 `["generic"]`，提示 Step 0.5 用 generic preset（11 base 类的子集）。

## 3. 多形态合并规则

一个项目可同时命中多个 architecture（最常见：`embedded + soa`、`web + cli`、`web + ml-pipeline`）。合并写入 `architectures[]`，并按下表决定推荐 preset：

| architectures 组合 | 推荐 preset | 备注 |
|---|---|---|
| `embedded` | `c-cpp-embedded` | 单嵌入式（也含 baremetal） |
| `embedded` + `soa` | `c-cpp-embedded-soa` | 用户首发场景 |
| `web` | `python-web-service` / `nodejs-web-service` 按语言挑 | |
| `frontend` | `frontend-spa` | |
| `web` + `frontend` | 各装一份 preset 的并集，但不去重 | |
| `cli` 单独 | `cli-tool` | |
| `ml-pipeline` | `data-pipeline` | |
| `generic` | `generic` | base 11 |

冲突时回显给用户由其拍板（"我们检测到 X 和 Y，推荐用 X-Y preset；如果你更想聚焦 Z，请回复 swap-preset"）。

## 4. risk_focus 字段语义

`risk_focus[]` 不是 finding category，而是"这次审查的着重点"提示，给 reviewer 在裁决严重度时做权重。例如 `risk_focus=["memory-safety"]` 时，reviewer 对 `memory-safety` 类 finding 起判 severity 默认 `high` 而不是 `medium`。

risk_focus 与 review_checklist 是正交的：checklist 决定"看哪些 category"，risk_focus 决定"哪些 category 更要紧"。

## 5. 已知限制

- 仅看顶层结构，不深扫子目录的 mono-repo（多包项目可能漏检子包架构差异）
- 不解析 `.gitignore` 之外被排除的二进制 / vendor 目录
- 自动检测可能误报或漏报；**Step 0.5 的用户确认是兜底闸门**

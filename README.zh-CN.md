# garage-agent

[English](README.md) | **中文**

<p align="center">
  <a href="https://github.com/hujianbest/garage-agent/actions/workflows/test.yml"><img src="https://github.com/hujianbest/garage-agent/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License: Apache 2.0"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://github.com/hujianbest/garage-agent/releases/tag/v0.1.0"><img src="https://img.shields.io/badge/release-v0.1.0-orange.svg" alt="Release v0.1.0"></a>
  <a href="CODE_OF_CONDUCT.md"><img src="https://img.shields.io/badge/code%20of%20conduct-Contributor%20Covenant-ff69b4.svg" alt="Code of Conduct"></a>
</p>

> **本地优先的 Agent 能力之家——存放你的 skills、knowledge、experience。**
> 在 Claude Code、Cursor、OpenCode 上都能用，数据留在你自己的仓库里，能力跟着你换宿主，每完成一件事，系统就比上次更聪明一点。

`garage-agent` 是为**独立创作者**准备的：你不必在"被一个 IDE 永远绑死"和"每次对话都从零开始"之间二选一。它把 Agent 能力当作**长在工作里的东西**——session 沉淀成记忆，记忆长成 skills，skills 打包成 packs，packs 跟着你走。

```
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│   sessions  ─►  knowledge + experience  ─►  skills + packs    │
│       ▲                    │                       │          │
│       │                    ▼                       ▼          │
│       └──── host context ◄──── garage sync ◄──── publish      │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## 为什么是 garage-agent

| | 没有 garage-agent | 有 garage-agent |
|---|---|---|
| **你的数据** | 锁在某个宿主的 session 数据库里 | `.garage/` 下的纯文本文件，在你自己仓库里 |
| **换宿主** | 一切重新教 | 一句 `garage init --hosts <new-host>`，skills + 记忆全跟过来 |
| **学到的东西** | 对话结束就消失 | 自动提炼成 `knowledge/` / `experience/`，由你审 |
| **分享能力** | 复制粘贴 prompt 到 Notion | `garage pack publish --to <git-url>`，自带脱敏 + 来源标记 |
| **车库的承诺** | 一个有聊天框的黑箱 | 一个你能读、能改、能传下去的工坊 |

## 核心特性

- **本地优先**——每个 session、knowledge 条目、experience 记录都是 `.garage/` 下可读的 Markdown / JSON / YAML 文件。明天不用 garage-agent 了，数据在任何文本编辑器里都还能打开。
- **三个 first-class 宿主**——Claude Code、Cursor、OpenCode。同一套 pack、同一套 skills、同一份记忆——`garage init --hosts claude,cursor,opencode --yes` 一次物化到三个宿主的原生目录。
- **完整的记忆飞轮**——`garage sync` 把 top-N knowledge + 最近 experience 推到每个宿主的 context surface（`CLAUDE.md` / `.cursor/rules/garage-context.mdc` / `.opencode/AGENTS.md`）；`garage session import --from <host>` 把宿主对话历史回流给系统提取。
- **能跟你走的 skill packs**——v0.1.0 自带 5 个 pack（`garage` / `coding` / `writing` / `search` / `code-audit`），共 **42 个 skill + 5 个 agent**（`garage` 3 个 + `code-audit` 2 个）。任意 git URL 装别人的 pack；用 `garage pack publish` 发自己的。
- **系统会主动建议下一个 skill**——当同一个 `(problem_domain, tag)` 模式出现 5+ 次，`garage skill suggest` 会出 SKILL.md 草稿；`garage skill promote` 把草稿落到真正的 pack。
- **Workflow 召回**——`garage recall workflow --problem-domain cli-design` 返回历史上对类似问题真正奏效过的 skill 链路，按出现频次排。
- **隐私友好的分享**——`garage pack publish` 推送前自动扫敏感模式；`garage knowledge export --anonymize` 让你能分享所学但不泄漏机密。
- **人始终掌舵**——破坏性 / 共享性操作都要 opt-in（`--yes` / `--force` / `--anonymize`）。系统建议，你拍板。

## v0.1.0 内含

| Pack | 版本 | Skills | Agents | 用途 |
|---|---|---|---|---|
| `packs/garage/` | 0.3.0 | 3 | 3 | 入门三件套（`garage-hello` / `find-skills` / `writing-skills`）+ 生产 agent（`code-review-agent` / `blog-writing-agent` / `garage-sample-agent`） |
| `packs/coding/` | 0.5.0 | 29 | 0 | 完整 HarnessFlow 工程工作流（spec → design → tasks → TDD → review → finalize），反向同步自 `harness-flow` main（对齐上游 v0.6.0 能力集） |
| `packs/writing/` | 0.2.0 | 5 | 0 | `blog-writing` / `humanizer-zh` / `hv-analysis` / `khazix-writer` / `magazine-web-ppt` |
| `packs/search/` | 0.1.0 | 1 | 0 | `ai-weekly`（X/Twitter 中文周报） |
| `packs/code-audit/` | 0.1.0 | 4 | 2 | 存量代码 bug 审查（四 skill + reviewer/verifier 双 agent） |

`garage init --hosts all` 一次物化 **126 个 skill 文件 + 10 个 agent 文件**（42 skills × 3 hosts；agent 仅装到 claude + opencode——Cursor 暂无 agent surface）。

## 安装

`garage-agent` 需要 Python 3.11+ 和 `uv`（推荐）或 `pip`。

```bash
# clone + 在 uv 管理的隔离 venv 里安装（推荐）
git clone https://github.com/hujianbest/garage-agent.git
cd garage-agent
uv sync
uv run garage --help

# 或者，从 clone 里 pip editable 安装
pip install -e .

# PyPI（一旦发布——见 release notes 状态）
pip install garage-agent
```

> PyPI 包名是 **`garage-agent`**（`pip install garage-agent`），但 Python import 路径是 **`garage_os`**（`import garage_os`）。和 Pillow / `import PIL` 是同一个 pattern。

## 60 秒上手

```bash
# 1) 把 4 个 pack 一次物化到 Claude Code + Cursor + OpenCode
garage init --hosts claude,cursor,opencode --yes

# 2) 看看落地了什么
garage status

# 3) 把 top-N knowledge + 最近 experience 推到每个宿主的 context surface
garage sync --hosts claude,cursor,opencode

# 4) 几次对话之后，把宿主历史回流给系统提取
garage session import --from claude --all

# 5) 问：历史上对类似问题哪个 workflow 真奏效过？
garage recall workflow --problem-domain cli-design

# 6) 再问：系统从我的模式里挖出了哪些可以变成 skill 的东西？
garage skill suggest --rescan
```

到这就完了——在同一个目录打开 Claude Code / Cursor / OpenCode，skills 和记忆都已经在了。

## 飞轮怎么转

1. **你工作。** 在你喜欢的宿主里聊。`garage session import` 把对话读回。
2. **系统提炼。** 重复出现的模式和决策变成 `knowledge/` 候选（decision / pattern / solution / style）和 `experience/` 记录。
3. **你审。** 没有 `garage memory review` 通过，任何东西都不进长期记忆。User-pact 写得很明白：方向盘在人手里。
4. **系统反推。** `garage sync` 把你的 top-N knowledge 写进 `CLAUDE.md` / `.cursor/rules/garage-context.mdc` / `.opencode/AGENTS.md`，下次新对话开局就已经知道你知道的事。
5. **模式变 skill。** 当 5+ 次 session 命中同一个 `(problem_domain, tag)` 桶，`garage skill suggest` 出草稿；你审、用 `hf-test-driven-dev` 打磨、`garage skill promote` 落到 pack。
6. **Skill 变共享物。** `garage pack publish --to <git-url>` 发布前自动扫敏感模式 + 提示 force-push 风险；别人 `garage pack install <git-url>` 拉走。

## Pack 生命周期

```bash
# 从任意 git URL 安装别人的 pack
garage pack install https://github.com/<user>/<their-pack>.git

# 列出已装 pack（从 URL 装的会显示 source_url）
garage pack ls

# 从 source_url 拉取并更新
garage pack update <pack-id> --yes

# 发布（敏感模式扫描 + force-push 提示 + 7 类匿名规则）
garage pack publish <pack-id> --to https://github.com/<you>/<pack-name>.git --yes

# 干净卸载（反向卸下每个宿主目录里的副本）
garage pack uninstall <pack-id> --yes

# 把所学脱敏导出
garage knowledge export --anonymize
```

## 顶层 CLI 速查

| 命令 | 用途 |
|---|---|
| `garage init` | 在当前项目初始化 Garage + 把 packs 物化到宿主 |
| `garage status` | 看已装内容、待审条目、stale 状态 |
| `garage run <skill>` | 通过宿主 adapter 执行 skill |
| `garage sync` | 把 top-N 记忆推到宿主 context surface |
| `garage session import` | 把宿主对话历史回流给系统提取 |
| `garage memory review` | 审通 / 拒绝提炼出的 knowledge 候选 |
| `garage knowledge add` / `knowledge edit` / `knowledge show` / `knowledge delete` | 写作 / 编辑 / 查看 / 删除 knowledge 条目 |
| `garage knowledge search` / `knowledge list` / `knowledge link` / `knowledge graph` | 召回、列出、连接 knowledge 条目（F006 图） |
| `garage knowledge export` | 匿名化 tarball 导出 |
| `garage experience add` / `experience show` / `experience delete` | 写作 experience 记录 |
| `garage pack install` / `pack ls` / `pack uninstall` / `pack update` / `pack publish` | 完整 pack 生命周期 |
| `garage skill suggest` | 列出系统建议的 skill 草稿 |
| `garage skill promote` | 把草稿提升成正式 pack skill |
| `garage recall workflow` | 基于历史 experience 推荐 skill 链路 |
| `garage recommend` | 为当前任务推荐 knowledge 条目 |

任何命令加 `--help` 看完整参数。

## 文档

| 入口 | 内容 |
|---|---|
| [用户指南](docs/guides/garage-agent-user-guide.md) | 端到端走完每个命令，含可复制的例子 |
| [灵魂文档](docs/soul/) | 项目的**为什么**：[`manifesto.md`](docs/soul/manifesto.md)、[`user-pact.md`](docs/soul/user-pact.md)、[`design-principles.md`](docs/soul/design-principles.md)、[`growth-strategy.md`](docs/soul/growth-strategy.md) |
| [Skill 写作原则](docs/principles/skill-anatomy.md) | 写或改 skill 之前必读 |
| [Pack 契约](packs/README.md) | `pack.json` schema、目录布局、host installer 行为 |
| [Feature specs](docs/features/) | F001–F014 规格（"做了什么"的存档） |
| [Release Notes](RELEASE_NOTES.md) | 每个 cycle 的用户可见变化 |
| [贡献指南](CONTRIBUTING.md) | AHE / HF workflow、开发环境、PR checklist、文件触碰边界 |
| [安全](SECURITY.md) | 通过 GitHub Security Advisory 上报漏洞 |

## 仓库地图

| 路径 | 用途 |
|---|---|
| [`packs/`](packs/) | 可分发 packs（single source of truth） |
| [`src/garage_os/`](src/garage_os/) | Python runtime：types、storage、runtime、knowledge、adapter（host installer + sync）、tools、platform |
| [`.garage/`](.garage/) | 工作区运行时状态（sessions / knowledge / experience / manifests / contracts / config） |
| [`docs/`](docs/) | 灵魂文档、specs、designs、reviews、approvals、guides、principles |
| [`tests/`](tests/) | 约 1045 个测试，目录结构与 `src/garage_os/` 一一对应 |
| [`AGENTS.md`](AGENTS.md) | 面向 Agent 的项目约定 + 开发参考 |
| [`RELEASE_NOTES.md`](RELEASE_NOTES.md) | F001 → F014 cycle 变更日志 |

## 路线图

v0.1.0 关闭了 14 个交付 cycle（F001–F014）。当前进度对照愿景：

```
信念 1  数据归你   █████████████████████████████████  5/5  ✅
信念 2  宿主可换   █████████████████████████          4/5  ⚠️ 第 4 个宿主仍要改源码
信念 3  渐进增强   █████████████████████████████████  5/5  ✅
信念 4  人机共生   █████████████████████████████████  5/5  ✅ 飞轮闭环
信念 5  可传承     █████████████████████████████████  5/5  ✅ install / update / publish / 匿名导出

Stage 1  工具箱   ████████████████████  100%
Stage 2  记忆体   ████████████████████  100%
Stage 3  工匠     █████████████          65%   ← skill mining 已上线，仍需手动打磨
Stage 4  生态     ████████               40%   ← lifecycle 完整；签名 + 发现仍待做
```

**v0.2 候选**（按优先级）：

1. `pack update --preserve-local-edits` 真 3-way merge
2. 可插拔宿主 registry（去掉第 4 个宿主必须改源码的约束）
3. Pack 签名 / GPG + `garage pack search` 中央发现
4. 跨机器 `garage sync`，含 git-aware 合并
5. `ruff` + `mypy` 清理 → 重新作为 blocking CI job
6. Cursor session 历史 reader（当前是 stub）

完整缺口分析见 [`docs/planning/`](docs/planning/)。

## 关于名字

车库是很多东西"还没打磨好之前"开始的地方——离问题最近，靠迭代成型，能长成真东西又不会因此丢掉自己的样子。`garage-agent` 想表达的就是这个：你的 Agent 能力应该**手工搭起来**、**随时间复利**，最后**走出车库**，但不会因为换工具而被丢掉。

它故意不是 SaaS、不是绑死单宿主的外壳、不是大而全的通用框架、也不是把判断完全交给自动化的全自动驾驶。它是一间工坊。

## 参与贡献

当前最有价值的外部贡献方向：workflow 质量、宿主可迁移性、文档清晰度、runtime 稳定性、真实使用示例。

- 提非琐碎 PR 之前先读 [`CONTRIBUTING.md`](CONTRIBUTING.md)
- 实质性改动请走本仓库自己 dogfood 的 AHE / HF workflow（`docs/features/Fxxx-*.md` spec → `docs/designs/` design → `docs/tasks/` tasks → 实现 + 测试 → `docs/reviews/` 自评 → `docs/approvals/` finalize）
- 请友好。[行为准则](CODE_OF_CONDUCT.md)采用 Contributor Covenant 2.1。
- 安全问题：**不要**开公开 issue——见 [`SECURITY.md`](SECURITY.md)。

## License

[Apache License 2.0](LICENSE)。选这个 license 是为了显式的专利授权 + 对下游友好，与 manifesto "数据归你、技能归你、可分享" 一致。

## 致谢

`garage-agent` 站在开源 agent 社区的肩膀上。`packs/coding/` 里的 HarnessFlow 工作流链反向同步自 [`hujianbest/harness-flow`](https://github.com/hujianbest/harness-flow)。设计影响在 [`docs/wiki/`](docs/wiki/) 里诚实记录，包括对 Hermes Agent、OpenSpec、gstack、get-shit-done、longtaskforagent、Superpowers 的对比分析。

献给所有想要自己的 Agent **记得上个月**、**知道自己的风格**、**换工具时一起搬家**的人。

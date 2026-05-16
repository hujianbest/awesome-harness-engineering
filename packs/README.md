# `packs/` — Garage 自带 Pack 集合

`packs/` 是 Garage 仓库内置的 **skills + agents 源**目录，对应 spec `F007 §11.3` 的目录契约。

## 关系

```
源（宿主无关）：     packs/<pack-id>/skills/<skill-name>/SKILL.md
                    packs/<pack-id>/agents/<agent-name>.md
                    packs/<pack-id>/pack.json
                    packs/<pack-id>/README.md

动作：              garage init --hosts claude,cursor,opencode
                    在执行 cwd 把 packs/ 内容物化到下列宿主目录
                    └── .claude/skills/...   .opencode/skills/...   .cursor/skills/...
                    └── .garage/config/host-installer.json   ← 安装清单
```

## 目录约定

每个 pack 是一个一级子目录：

```
packs/<pack-id>/
├── pack.json           # 元描述（schema_version=1）
├── README.md           # 人类可读概述
├── skills/             # 0..N 个 skill 子目录
│   └── <skill-id>/
│       └── SKILL.md    # 必须遵循 docs/principles/skill-anatomy.md
└── agents/             # 0..N 个 agent 文件
    └── <agent-id>.md
```

`pack.json` 字段：

| 字段 | 必需 | 说明 |
|---|---|---|
| `schema_version` | ✅ | 固定 `1` |
| `pack_id` | ✅ | 必须等于目录名 |
| `version` | ✅ | pack 自身版本（语义版本字符串） |
| `description` | ✅ | 人类可读说明 |
| `skills[]` | ✅ | 本 pack 包含的 skill id 清单（与 `skills/<skill-id>/SKILL.md` 一一对应；`pack_discovery` 启动时校验） |
| `agents[]` | ✅ | 本 pack 包含的 agent id 清单（与 `agents/<agent-id>.md` 一一对应；可为空数组） |

## 当前 packs

| Pack | 用途 | skills | agents | 状态 |
|---|---|---|---|---|
| `packs/garage/` | Getting-started 三件套 + F011 三个 production agent | 3 | 3 | ✅ 已落盘（F007 + F008 + F011 0.3.0） |
| `packs/coding/` | HarnessFlow 工程工作流 family：28 hf-* + using-hf-workflow（per-skill self-contained） | 29 | 0 | ✅ 已落盘（v0.5.0，reverse-sync harness-flow main / v0.6.0-aligned） |
| `packs/search/` | 信息聚合 / curation family：ai-weekly | 1 | 0 | ✅ 已落盘（PR#28 search hotfix） |
| `packs/writing/` | 内容创作 family：blog-writing / humanizer-zh / hv-analysis / khazix-writer / magazine-web-ppt + family-level prompts/横纵分析法.md | 5 | 0 | ✅ 已落盘（F008 + magazine-web-ppt） |
| `packs/code-audit/` | 存量代码 bug 审查 family：audit-planner / audit-reviewer / audit-verifier / audit-reporter + 双 agent（reviewer 一审 + verifier 独立复核） | 4 | 2 | ✅ Slice A 已落盘（pack 骨架；Slice B/C/D 渲染脚本待跟进） |

合计 5 个 pack × **42 个 skill** × 3 个宿主 = `garage init --hosts all` 物化 126 个 skill 文件 + 10 个 agent 文件（5 agent × 2 hosts；agent 仅装到 claude / opencode；cursor 无 agent surface）。

未来计划（F010+）：

- `packs/product-insights/` — product discovery 系列 skill 沉淀目标（待真实内容物到位后开 cycle）
- `garage uninstall` / `garage update` — 安装逆向操作 + packs 内容拉新流程
- D7 安装管道扩展为递归 `references/` / `evals/` / `scripts/` 子目录（让下游宿主装后引用直接可达，闭合 design ADR-D8-4 接受的"文档级提示"工程边界）
- F009 carry-forward I-1 (CON-902 phase 1+3 body 守门) + I-2 (VersionManager host-installer migration 链注册)

## `.agents/skills/` 已删除（F008 ADR-D8-2 候选 C）

F008 cycle 把 `.agents/skills/` 整个删除，本仓库自身贡献者首次 clone 后通过 dogfood `garage init --hosts cursor,claude` 在仓库根产生 `.cursor/skills/` + `.claude/skills/`（已在 `.gitignore` 排除）作为 IDE 加载入口。详见 `AGENTS.md "本仓库自身 IDE 加载入口"` 段。

## Dogfood 与下游用法

**在 Garage 仓库自身 dogfood**：

```bash
# 在 Garage 仓库根目录执行
garage init --hosts claude
# → 会在 .claude/skills/ 下出现 packs/garage/skills/* 的副本
```

**在下游用户项目使用**：

```bash
# 用户在自己项目的根目录执行
cd ~/projects/my-app
garage init --hosts claude,cursor
# → 会在 my-app/.claude/skills/ 与 my-app/.cursor/skills/ 下出现 packs/garage/skills/* 的副本
# → 同时写入 my-app/.garage/config/host-installer.json 安装清单
```

详见 `docs/guides/garage-agent-user-guide.md` 的 "Pack & Host Installer" 段。

## Install Scope（F009 新增）

F009 在 `garage init` 加 `--scope` flag，让用户选**装到哪里**：

| Scope | 落盘位置 | 用途 |
|---|---|---|
| `project`（默认） | `<cwd>/.{host}/skills/` | 跟着项目走；`git status` 可见；F007/F008 行为完全等价（CON-901） |
| `user` | `~/.{host}/skills/` 等家目录 | 跟着你走；solo creator 跨多客户仓库共享同一套 skills；不入项目 git |

**3 种使用方式**：

```bash
# (1) 全局 --scope flag (新增): 全部 host 用同一 scope
garage init --hosts all --scope user
# → 装到 ~/.claude/skills/ + ~/.cursor/skills/ + ~/.config/opencode/skills/ (XDG default)

# (2) per-host 后缀语法 (新增): 每个 host 独立 scope, 覆盖 --scope 全局默认
garage init --hosts claude:user,cursor:project
# → claude → ~/.claude/skills/, cursor → <cwd>/.cursor/skills/

# (3) 交互式两轮 (新增): TTY 用户首选, candidate C 三个开关
garage init                     # 不带 --hosts / --yes / --scope, TTY 进入交互
# 第一轮: 选哪些宿主?
# 第二轮: a (all project, default 一键回车) / u (all user) / p (per-host 逐个询问)
```

**何时选哪个**：

- **project**（默认）— 与团队共享、与项目绑定（如 hf-* workflow 装到团队仓库）
- **user** — 跟着自己跨项目复用（如个人写博客 / 横纵分析 skill 装到家目录，所有项目都能用）
- **混合（per-host）** — 比如 hf-* workflow 装到 user scope（跟人走），团队特定 skill 装到 project（跟项目走）

**三家宿主 user scope 路径**（来自各家官方文档）：

| Host | User scope path |
|---|---|
| Claude Code | `~/.claude/skills/<id>/SKILL.md` + `~/.claude/agents/<id>.md` |
| OpenCode | `~/.config/opencode/skills/<id>/SKILL.md` (XDG default) + `~/.config/opencode/agent/<id>.md` |
| Cursor | `~/.cursor/skills/<id>/SKILL.md`（无 agent surface） |

详见 `docs/features/F009-garage-init-scope-selection.md`（已批准 spec）+ `docs/designs/2026-04-23-garage-init-scope-selection-design.md`（11 ADR + 完整调研锚点）。

## 不变量

- `packs/` 目录及其内容物**不得**包含任何宿主特定术语（`.claude/` / `.cursor/` / `.opencode/` / `claude-code` 等），由 NFR-701 自动测试守护。
- 同名 skill 在多个 pack 中共存会导致 `garage init` 退出码 2 + stderr 列出冲突 source/dest（FR-704 验收 #4）。
- 缺失 `packs/` 目录或 packs 为空时，`garage init` 仍正常退出 0、不创建任何宿主目录、stdout 提示 `No packs found under packs/`。

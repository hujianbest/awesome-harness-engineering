# AGENTS

## AHE 文档约定

- 在本仓库的 AHE workflow 中，`docs/features/` 下的 `Fxxx` 文档就是 `specs`。
- 当提到 `spec`、`specs` 或"规格"时，默认指 `docs/features/` 的 feature specs，而不是 `docs/tasks/`。

## Skill 写作原则

`docs/principles/skill-anatomy.md` 定义所有 Garage skill 的目标态写法，包括：

- 核心 7 原则（description 是分类器、主文件要短、边界必须显式等）
- 目录 anatomy（SKILL.md、references/、evals/、scripts/、assets/）
- 章节骨架（When to Use、Workflow、Output Contract、Red Flags、Verification 等）
- 演化与版本管理机制

新增或重写任何 skill 时，必须遵循此文档。

## 项目灵魂

`docs/soul/` 下存放 Garage 的核心信念和承诺，是所有设计决策的价值锚点：

- `manifesto.md` — 愿景宣言：Garage 为什么存在
- `user-pact.md` — 用户契约：Garage 对用户的承诺
- `design-principles.md` — 设计原则：架构决策的判断标准
- `growth-strategy.md` — 成长策略：系统怎么从简单变复杂

当设计决策出现价值冲突时，回溯到这里做判断。

## garage-agent

- 运行时数据存储: .garage/
- 平台配置: .garage/config/platform.json
- 宿主适配器配置: .garage/config/host-adapter.json
- **Pack 安装清单（F007/F008/F009）**: `.garage/config/host-installer.json`（**schema_version=2** since F009；F007/F008 schema 1 manifest 由 `read_manifest` 自动 migrate；`garage init --hosts ...` 写入；记录已安装宿主集合 + Garage-owned 文件清单 + content_hash + scope，作为幂等再运行凭证）
- 平台契约: .garage/contracts/
- 技术栈: Python 3.11+ (Poetry)

## Packs & Host Installer (F007/F008/F009)

Garage 自带的可分发 skills + agents 沉淀在仓库 `packs/<pack-id>/` 下；`garage init --hosts ...` 把它们物化到下游项目里 Claude Code / OpenCode / Cursor 三家宿主原生目录。

### 当前 packs（F008 + PR#25 + search hotfix 落地后）

| Pack | version | skills | agents | 用途 |
|---|---|---|---|---|
| `packs/garage/` | `0.3.0` | 3 | 3 | Getting-started 三件套（garage-hello / find-skills / writing-skills）+ 3 agent（garage-sample-agent + code-review-agent + blog-writing-agent，F011 落地）|
| `packs/coding/` | `0.5.0` | 29 | 0 | HarnessFlow 工程工作流 family（28 hf-* + using-hf-workflow；per-skill self-contained；reverse-sync 自 hujianbest/harness-flow main，对齐上游 v0.6.0 能力集；garage-side 第一方增量 = hf-workflow-router step 3.5 F014 Workflow Recall）|
| `packs/search/` | `0.1.0` | 1 | 0 | 信息聚合 / curation family：ai-weekly（X/Twitter 周报，Priority 1/2/3 中文报告）|
| `packs/writing/` | `0.2.0` | 5 | 0 | 内容创作 family：blog-writing / humanizer-zh / hv-analysis / khazix-writer / magazine-web-ppt + family-level prompts/横纵分析法.md |
| `packs/code-audit/` | `0.3.0` | 4 | 2 | 存量代码 bug 审查 family：audit-planner / audit-reviewer / audit-verifier / audit-reporter + 双 agent；按模块切分、双 agent 串行确认、输出 HTML（必需）+ Excel（可选）报告；**v0.3.0：每模块独立上下文一审（per-module-context-protocol.md）—— audit-reviewer 单次只扫一个模块、orchestrator agent 完成即移交用户开新会话续跑下一模块，避免 LLM 上下文压缩 / 滑窗淘汰导致后段模块命中率下降；默认 budgets 收紧 token 30000→12000、files 20→8；audit-planner 新增 partition strategy 4（深度目录树切分），plan.json 新增 partition_strategy 字段；新增 reviewer-agent 参数 --resume / --module / --auto-loop（CI 降级）。** v0.2.0：audit-planner 先识别项目语言+架构（C/C++ embedded SOA / Python web / frontend SPA / generic 等）→ 推荐针对性 review_checklist 与用户握手确认 → 切模块；finding.category 由 plan.json review_checklist 动态决定（不再固定 11 类）；report header 展示 profile + checklist；旧 plan.json 缺字段时回退 base 11 完全兼容 |

合计 5 个 pack × 42 个 skill × 3 个宿主 = `garage init --hosts all` 物化 126 个 skill 文件 + 10 个 agent 文件（5 agent × 2 hosts；agent 仅装到 claude / opencode）。

### 入口指针（FR-710 5 分钟冷读链）

| 文档 | 角色 |
|---|---|
| `packs/README.md` | 顶层契约：pack 目录结构、`pack.json` schema、与宿主关系、不变量 |
| `packs/<pack-id>/README.md` | 每个 pack 的概述 + skill/agent 清单（强制） |
| `docs/guides/garage-agent-user-guide.md` "Packs、Skills 和 Agents" 段 | 端到端用法（交互/非交互/extend mode、退出码、宿主路径表、风险） |
| `docs/features/F007-garage-packs-and-host-installer.md` | F007 已批准规格（packs/ 目录契约 + `garage init --hosts ...` 安装管道） |
| `docs/features/F008-garage-coding-pack-and-writing-pack.md` | F008 已批准规格（把 `.agents/skills/` 物化为 packs 内容物）|
| `docs/features/F009-garage-init-scope-selection.md` | F009 已批准规格（`garage init` 双 scope project/user + 交互式 scope 选择）|

代码入口：`src/garage_os/adapter/installer/`（与 F001 `host_adapter.py` 同包但接口独立，详见 design ADR-D7-1）。三个 first-class host adapter 在 `src/garage_os/adapter/installer/hosts/{claude,opencode,cursor}.py`。

### 本仓库自身 IDE 加载入口（F008 ADR-D8-2 候选 C）

F008 cycle 把 `.agents/skills/` 整个删除，改为 dogfood 安装产物作为 IDE 加载入口。**首次 clone 本仓库的贡献者**必须在仓库根跑一次 dogfood 才能在 IDE 内加载到这 42 个 skill：

```bash
cd /path/to/garage-agent
garage init --hosts cursor,claude
# → 在仓库根 dogfood 出 .cursor/skills/ + .claude/skills/，IDE 即可加载 42 个 skill
# 注：.cursor/skills/ + .claude/skills/ 已在 .gitignore 内排除，不入 git 追踪
# → AGENTS.md / README.md 更新后无需再次跑 dogfood，但 packs/ 内容物变化时需要重跑
```

为什么这么设计？

- 单源不变量最强：`packs/<pack-id>/` 是唯一权威源，`.cursor/skills/` 与 `.claude/skills/` 在 git 视角是 dogfood 安装产物（与下游用户体验完全一致）
- 验证 D7 安装管道可用：本仓库自己跑 `garage init --hosts cursor,claude` 就是对 F007 + F008 联合最强证据
- 无平台 symlink 风险（与 candidate A 的 git symlink 路径相比，跨平台兼容更强）

详见 design ADR-D8-2（`docs/designs/2026-04-22-garage-coding-pack-and-writing-pack-design.md`）。

### Install Scope（F009 新增）

F009 在 `garage init` 加 `--scope` flag，让 solo creator 跨多客户仓库使用同一套 packs：

- `--scope project`（默认，CON-901 兼容）：装到 `<cwd>/.{host}/skills/`，与 F007/F008 行为完全等价
- `--scope user`：装到 `~/.{host}/skills/` 等家目录（claude `~/.claude/skills/`，opencode XDG `~/.config/opencode/skills/`，cursor `~/.cursor/skills/`）
- per-host override：`--hosts claude:user,cursor:project` 让每个 host 独立指定 scope
- 交互式两轮：TTY 下 `garage init` 第一轮选宿主、第二轮 a/u/p 三个开关（default `a` = all project = F007/F008 行为）

**dogfood 路径不受影响**：本仓库自身 `garage init --hosts cursor,claude` 仍默认 project scope（无 `--scope`），与 F008 ADR-D8-2 candidate C 完全等价（NFR-901 Dogfood 不变性硬门槛由 sentinel test 守门）。

详见 spec `docs/features/F009-garage-init-scope-selection.md` + design `docs/designs/2026-04-23-garage-init-scope-selection-design.md`（11 ADR + 完整调研锚点）+ user guide "Pack & Host Installer > Install Scope" 段。

## Memory Sync (F010)

F010 让 F003-F006 build 的整个 memory 子系统（`.garage/knowledge/` + `.garage/experience/`）**真正进入用户日常 host 对话**：

- `garage sync` push 路径：top-12 knowledge + top-5 experience 编译到三家宿主原生 context surface（`CLAUDE.md` / `.cursor/rules/garage-context.mdc` / `.opencode/AGENTS.md`），用户在 IDE 开新对话时自动看到 Garage 知识
- `garage session import --from <host>` pull 路径：把宿主对话历史 ingest 成 Garage SessionState，触发 F003 自动提取链 → candidate review → 知识入库

### 三家宿主路径表

| Host | project scope | user scope |
|---|---|---|
| Claude Code | `<cwd>/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| Cursor | `<cwd>/.cursor/rules/garage-context.mdc` (含 `alwaysApply: true` front matter) | `~/.cursor/rules/garage-context.mdc` |
| OpenCode | `<cwd>/.opencode/AGENTS.md` | `~/.config/opencode/AGENTS.md` (XDG default) |

### `SessionContext.metadata` F010 占用 key

| key | 类型 | 用途 |
|---|---|---|
| `imported_from` | `str` | provenance: `"<host>:<conversation_id>"` (e.g. `"claude-code:abc123"`) |
| `tags` | `list[str]` | F003 `_build_signals` 强 signal #1 (priority 0.62) — ingest 灌入 `["ingested", host, ...]` |
| `problem_domain` | `str` | F003 `_build_signals` 强 signal #2 (priority 0.72) — ingest 用 first user message 前 100 char |

### host_id alias

| alias | canonical (ingest) |
|---|---|
| `claude` | `claude-code` |
| `claude-code` | `claude-code` |
| `opencode` | `opencode` |
| `cursor` | `cursor` (deferred to F010 D-1010, raises NotImplementedError) |

### 已知限制 / 后续工作

- Cursor history 路径未稳定 (HYP-1005 Low confidence) → `cursor` reader 是 stub, deferred 到 D-1010
- `garage sync` 是显式触发, 无自动 file-watcher (F012-D 候选)
- ingest 不绕过 F003 candidate 审批 (CON-1004 + B5 user-pact)

详见 spec `docs/features/F010-garage-context-handoff-and-session-ingest.md` + design `docs/designs/2026-04-24-garage-context-handoff-and-session-ingest-design.md`（13 ADR + 10 INV + 7 sub-commit 分组）+ user guide "Sync & Session Import" 段。

## P1 Completion (F011)

F011 cycle 把 vision-gap planning § 2.2 三个 P1 candidate 在一个 cycle 内合做:

### A. KnowledgeType.STYLE 维度 (复活 Promise ② "知道你的编码风格")

- `KnowledgeType` enum 加 `STYLE = "style"` value
- `KnowledgeStore.TYPE_DIRECTORIES[STYLE] = "knowledge/style"`
- `garage knowledge add --type style --topic "Functional Python preference" --content "..."` 可用
- F010 sync compiler 自动 include STYLE 到 top-N (per-kind=4, ranking 在 pattern 之后)
- CLAUDE.md 等 host context surface 自动出现 `### Recent Style Preferences` 段

### B. 2 个 production agent (启动 Stage 3 工匠)

- `packs/garage/agents/code-review-agent.md`: 组合 hf-code-review + user style entries
- `packs/garage/agents/blog-writing-agent.md`: 组合 blog-writing + humanizer-zh + (可选) hv-analysis
- `packs/garage/pack.json` version 0.2.0 → 0.3.0; agents 数 1 → 3
- `garage init --hosts <list>` 自动装到 `.claude/agents/` + `.opencode/agent/` (cursor 无 agent surface)

### C. `garage pack install <git-url>` (B5 可传承 2/5 → 3.5/5)

- `garage pack install <git-url>`: shallow git clone (`--depth=1`) + 验证 pack.json + 装到 `<workspace>/packs/<pack-id>/` + 写 `source_url`
- `garage pack ls`: 列出已装 pack (id, version, source_url 或 'local')
- `pack.json` schema 加 optional `source_url` 字段 (向后兼容, F007 既有 packs 仍 valid)

详见 spec `docs/features/F011-style-dimension-and-production-agents-and-pack-install.md` + design `docs/designs/2026-04-24-style-dimension-and-production-agents-and-pack-install-design.md`。

## Pack Lifecycle (F012)

F012 把 F011 的 `garage pack install` + `garage pack ls` 扩展为完整 lifecycle:

### `garage pack uninstall <pack-id>` (FR-1201..1203)

```bash
garage pack uninstall my-pack             # interactive prompt
garage pack uninstall my-pack --yes       # skip prompt
garage pack uninstall my-pack --dry-run   # print plan, no changes
```

- 三步 transaction (plan / confirm / execute) — 反向 install + atomic rollback
- Touch boundary 严守 (CON-1205): 仅触碰 `packs/<id>/` + `host-installer.json` + host 目录映射文件; **不读不写** `sync-manifest.json` / `knowledge/` / `experience/` / `sessions/` / `contracts/` / `platform.json` / `host-adapter.json`
- F010 sidecar (`references/ assets/ evals/ scripts/`) 反向清

### `garage pack update <pack-id>` (FR-1204..1206)

```bash
garage pack update my-pack                          # interactive
garage pack update my-pack --yes                    # auto-confirm
garage pack update my-pack --preserve-local-edits   # warn (true 3-way merge deferred)
```

- 从 `pack.json source_url` 重新 shallow clone, 比对版本
- 同 → no-op; 不同 → atomic 替换 + `install_packs(force=True)` 反向同步 host
- 失败时滚回原版本

### `garage pack publish <pack-id> --to <git-url>` (FR-1207..1210)

```bash
garage pack publish my-pack --to https://github.com/me/my-pack.git --yes
garage pack publish my-pack --to <url> --force                        # bypass sensitive scan (B5 opt-in)
garage pack publish my-pack --to <url> --dry-run                      # build commit but no push
garage pack publish my-pack --to <url> --commit-author "Alice <a@x>"  # override author
garage pack publish my-pack --to <url> --no-update-source-url         # keep local source_url
```

- **隐私自检**: 默认扫 16 类文本扩展, 5 类 SENSITIVE_RULES (password / api_key / secret / token / private_key) 命中 → abort
- **Force-push 风险告知**: `git ls-remote` 检测后 prompt 显式 WARNING
- **作者决议**: `--commit-author` > `git config user.name/email` > fallback `Garage <garage-publish@local>`

### `garage knowledge export --anonymize` (FR-1211..1213)

```bash
garage knowledge export --anonymize                          # ~/.garage/exports/knowledge-<ts>.tar.gz
garage knowledge export --anonymize --output ./my-export     # custom output (workspace 内时 .gitignore warn)
garage knowledge export --anonymize --dry-run                # 仅 print 命中规则统计
```

- 7 类 ANONYMIZE_RULES (5 base 与 SENSITIVE_RULES 1:1 + email + sha1_hash 专属)
- Mixed strategy: KnowledgeStore.list_entries 拿 metadata + filesystem read 拿原 markdown bytes
- Front matter (id/topic/tags/date) 不动, 仅 body 脱敏
- 用户可在 `~/.garage/anonymize-patterns.txt` 加 extra regex (一行一条 + `#` 注释)

### F009 carry-forward: VersionManager registry (FR-1214)

F012-E 注册 host-installer schema 1→2 migration 到 `_MIGRATION_REGISTRY[(1, 2)]` (与 F001 platform.json / host-adapter.json 同模式); `VersionManager.SUPPORTED_VERSIONS = [1, 2]`. F009 既有 `read_manifest` fast-path 字节级不变 (双源等价).

详见 spec `docs/features/F012-pack-lifecycle-completion.md` + design `docs/designs/2026-04-25-pack-lifecycle-completion-design.md` (7 ADR + 9 INV)。

## Skill Mining Push (F013-A)

F013-A 把 F003-F006 的 memory 提取管道闭环上 **push 端** — 当系统在 N 次 session 里看见同一类 (problem_domain, tag-bucket) 重复出现, 主动建议 "这个 pattern 可以变成 skill", 半自动产 SKILL.md 草稿 + 嵌 hf-test-driven-dev 走完 promote.

### `garage skill suggest` (FR-1302)

```bash
garage skill suggest                            # list status=proposed by score desc
garage skill suggest --status promoted          # filter by status
garage skill suggest --id sg-XXX                # detail + SKILL.md preview
garage skill suggest --rescan                   # full re-scan + write new proposals
garage skill suggest --rescan --threshold 3     # rescan with custom N
garage skill suggest --threshold 3              # display filter only (no rescan)
garage skill suggest --purge-expired --yes      # physical delete expired
```

### `garage skill promote <suggestion-id>` (FR-1304)

```bash
garage skill promote sg-XXX                     # interactive [y/N] prompt + preview
garage skill promote sg-XXX --yes               # skip prompt
garage skill promote sg-XXX --dry-run           # preview only, no write
garage skill promote sg-XXX --target-pack coding  # default 'garage'
garage skill promote sg-XXX --reject [--yes]    # status=rejected with reason prompt
```

- 写入唯一通道 (INV-F13-1): `packs/<target>/skills/<suggested-name>/SKILL.md` 由 promote 生成
- **CON-1304 守门**: promote 不动 `packs/<target>/pack.json` 的 `skills[]` 列表; 用户走 `garage run hf-test-driven-dev` 路径自己加 (sentinel 测试守 byte-level)
- **CON-1305 守门**: promote echo `Run 'garage run <name>' to test, or 'garage run hf-test-driven-dev' to refine` 仅给路径, 不自动 invoke

### Pattern Detection (FR-1301)

聚类规则: 按 (problem_domain_key, frozenset(tag-bucket)) 分组; 同组内 unique session_id ≥ N (默认 5) 触发. 双源 problem_domain_key:
- ExperienceRecord: 直读 `record.problem_domain` (F004 既有顶层字段)
- KnowledgeEntry: 优先 `entry.front_matter["problem_domain"]`; fallback `entry.topic.split()[0]`

Hook 接入两个 caller 路径 (ADR-D13-3 r2 Cr-1):
- `SessionManager._trigger_memory_extraction` 末尾 (普通归档路径)
- `ingest/pipeline.py` 在 `extract_for_archived_session_id` 后 (`garage session import` 路径)
- 两路径都 try/except, hook 失败不阻断 archive / import (best-effort)

### Audit / Decay + `garage status` 显示

- proposed 30 天后归 expired (`run_audit` 自动跑); rejected 永久; promoted 永久; expired 可 purge
- `garage status` **始终**显 metadata 行 "Skill mining: scanned X / Y / Z (last scan: <ts>)" — 即使 Z=0 也显 (RSK-1301 兜底; 用户看见管道在工作)
- proposed > 0 时**额外**显 💡 提示行 (Im-6 r2)

### 配置 (Mi-1 r2 双根)

- 项目根 `.garage/skill-suggestions/{proposed/, accepted/, promoted/, rejected/, expired/}/<sg-id>.json` — suggestion 数据
- 用户根 `~/.garage/skill-mining-config.json` — 用户偏好 (threshold / expiry_days / hook_enabled / exclude_domains)
- platform 配置 `.garage/config/platform.json` `skill_mining.hook_enabled: bool` — fallback gate (默认 true; 设 false 可关 hook 仅留 CLI rescan)

### Carry-forward (F014+)

- 增量扫 (避免每次 archive 全量扫 1000+1000)
- NLP-based 模式相似度 (P1 启发式仅 frozenset(tags 前 2))
- 系统反向产 style skill (基于 KnowledgeType.STYLE 既有数据)

详见 spec `docs/features/F013-skill-mining-push.md` + design `docs/designs/2026-04-26-skill-mining-push-design.md` (7 ADR + 5 INV + 5 CON)。

## Workflow Recall (F014)

F014 把 hf-workflow-router 从 "纯静态决策" 升级到 "查历史路径主动建议": 当 ExperienceIndex 里有 ≥ 3 条同 (task_type, problem_domain) record 时, router step 3.5 (新插入, additive 不破坏既有 step 1-10) 调 `garage recall workflow --json`, 在 handoff 块附 advisory 段 — advisory only, 不改 router authoritative routing 决策权.

### `garage recall workflow` (FR-1402)

```bash
garage recall workflow --task-type implement                       # filter by task_type
garage recall workflow --problem-domain cli-design                 # filter by problem_domain
garage recall workflow --skill-id hf-design                        # take subseq after Z (Im-4 r2)
garage recall workflow --task-type X --problem-domain Y --top-k 5  # combined
garage recall workflow --problem-domain X --json                   # for router consumption
garage recall workflow --rebuild-cache                             # force full recompute
```

- 唯一通道写 `.garage/workflow-recall/{cache,last-indexed}.json` (INV-F14-2; 不动 packs/)
- 与 F006 `garage recommend` 完全独立 (CON-1405): recommend 推内容, recall workflow 推路径
- 阈值 N ≥ 3, 桶内 record 数不足时返回空 + 友好 msg
- `--skill-id Z` (Im-4 r2): 取 Z 第一次出现位置之后的子序列; Z 是序列最后一项 → 跳过

### Pattern Detection (FR-1401)

聚类规则: 按 (task_type, problem_domain) 配对分桶; 同桶内按 created_at desc 取最近 10 条; 提取 skill_ids 序列频率 (Counter); top-K (默认 3) 序列输出.

聚类源: `experience_index.list_records()` + Python filter on `record.task_type / record.problem_domain` (不调 `search(domain=)`, 因为 F004 的 search domain 过滤 `record.domain` 而非 `record.problem_domain`).

### WorkflowRecallHook 多 caller 接入 (Cr-1+Cr-2+Im-1 r2)

cache invalidate 在 4 处 ExperienceRecord 写入 caller 末尾 try/except invoke (与 F013-A SkillMiningHook 多 caller 接入同 pattern, best-effort 不阻断 caller):

| # | Caller | 接入位置 |
|---|---|---|
| 1 | `session_manager._trigger_memory_extraction` | 末尾 (F013-A SkillMiningHook 之后); F003 archive 路径兜底 |
| 2 | `cli.py _experience_add` | `experience_index.store(record)` 后 |
| 3 | `publisher.py` | if-else 末尾 (覆盖 store + update 两路径; Im-1 r2 修订) |
| 4 | `knowledge/integration.py` | `experience_index.store(experience)` 后 |

显式排除 (Cr-1 r2 USER-INPUT 选项 b): `cli.py:1172` (skill execution path; record 单位是 single skill 不是 cycle-level task); 用户用 `--rebuild-cache` 兜底.

### hf-workflow-router step 3.5 (FR-1403)

router 在既有 step 3 (支线信号) 与 step 4 (Profile) 之间插入 step 3.5 (additive, INV-F14-5 守门: 既有 step 1-10 + dogfood SHA baseline 一并守门). 详见 `packs/coding/skills/hf-workflow-router/SKILL.md` step 3.5 + `packs/coding/skills/hf-workflow-router/references/recall-integration.md`.

### `garage status` 显示 + 配置 (FR-1405)

- `garage status` 末尾加段: "Workflow recall: scanned X records / Y buckets / Z advisories (last scan: ...)" — 始终显 (RSK-1401: Z=0 也显, 用户看见管道在工作); cache stale 时附 "(stale, will rebuild on next recall call)"
- 配置: `~/.garage/skill-mining-config.json` (用户根, 与 F013-A 共享配置文件结构) 或 `.garage/config/platform.json` `workflow_recall.enabled: bool` (默认 true; 设 false 关 hook 仅留 CLI rescan)

### Carry-forward (F015+)

- D-1410: 增量扫 cache (当前全量重算 1000 record < 0.064s, 极不紧迫)
- D-1411: NLP-based skill_ids 序列相似度 (P1 启发式: tuple equality)
- D-1412: agent 自动组装 (`garage agent compose`); 当前 production agents 仍手写

详见 spec `docs/features/F014-workflow-recall.md` + design `docs/designs/2026-04-26-workflow-recall-design.md` (7 ADR + 5 INV + 5 CON)。

### garage-agent 开发者参考

#### 模块概览

garage-agent 的 Python 实现源码位于 `src/garage_os/`（兼容保留的包路径），由 7 个核心模块组成：

| 模块 | 路径 | 职责 |
|------|------|------|
| **types** | `src/garage_os/types/` | 核心类型定义：`SessionState`、`ArtifactReference`、`KnowledgeEntry`、`ExperienceRecord`、`Checkpoint` 等数据结构 |
| **storage** | `src/garage_os/storage/` | 文件存储基础设施：`FileStorage`（带文件锁的读写）、`AtomicWriter`（原子写入）、`FrontMatterParser`（YAML front matter 解析） |
| **runtime** | `src/garage_os/runtime/` | 运行时核心：`SessionManager`（会话生命周期）、`StateMachine`（状态机）、`SkillExecutor`（技能执行）、`ErrorHandler`（错误处理与重试）、`ArtifactBoardSync`（制品同步） |
| **knowledge** | `src/garage_os/knowledge/` | 知识管理：`KnowledgeStore`（知识条目 CRUD，markdown + front matter 存储）、`ExperienceIndex`（经验记录与索引）、`KnowledgeIntegration`（知识查询集成） |
| **adapter** | `src/garage_os/adapter/` | 宿主适配层：`HostAdapterProtocol`（运行时执行协议）、`ClaudeCodeAdapter`（运行时执行实现）；**`adapter/installer/` 子包（F007）**：`HostInstallAdapter` Protocol（安装期路径映射，与运行时 protocol 独立）、`HOST_REGISTRY` 三宿主、`pipeline.install_packs` 端到端 |
| **tools** | `src/garage_os/tools/` | 工具网关：`ToolRegistry`（工具注册与发现）、`ToolGateway`（工具调用记录与 mock 执行） |
| **platform** | `src/garage_os/platform/` | 平台契约管理：`VersionManager`（版本检测、兼容性检查、schema 迁移） |

模块依赖关系（自底向上）：
```
types → storage → runtime → knowledge
                  ↑            ↑
              adapter ← tools ← platform
```

#### 关键命令

```bash
# 运行全部测试
uv run pytest tests/ -q

# 运行指定模块测试
uv run pytest tests/runtime/ -q
uv run pytest tests/knowledge/ -q

# 运行性能基准测试
uv run python scripts/benchmark.py

# 类型检查
uv run mypy src/

# 代码风格检查
uv run ruff check src/ tests/
```

#### .garage/ 目录结构

`.garage/` 是 garage-agent 的运行时数据目录，所有数据以文件形式存储，git 可追踪：

```
.garage/
├── README.md                              # 目录说明
├── config/
│   ├── platform.json                      # 平台配置（schema_version, storage_mode, session_timeout 等）
│   ├── host-adapter.json                  # 宿主适配器配置（host_type, interaction_mode, capabilities）
│   └── tools/
│       └── registered-tools.yaml          # 已注册工具清单
├── contracts/
│   ├── session-manager-interface.yaml     # SessionManager 接口契约
│   ├── state-machine-interface.yaml       # StateMachine 接口契约
│   ├── skill-executor-interface.yaml      # SkillExecutor 接口契约
│   ├── knowledge-store-interface.yaml     # KnowledgeStore 接口契约
│   ├── host-adapter-interface.yaml        # HostAdapter 接口契约
│   ├── error-handler-interface.yaml       # ErrorHandler 接口契约
│   ├── tool-registry-interface.yaml       # ToolRegistry 接口契约
│   └── version-manager-interface.yaml     # VersionManager 接口契约
├── knowledge/
│   ├── .metadata/
│   │   └── index.json                     # 经验索引（中心索引）
│   ├── decisions/                         # 决策类知识条目（markdown + front matter）
│   ├── patterns/                          # 模式类知识条目
│   └── solutions/                         # 解决方案类知识条目
├── experience/
│   └── records/                           # 经验记录（JSON 格式）
└── sessions/
    ├── active/                            # 活跃会话
    └── archived/                          # 归档会话
```

- **零配置启动**：首次使用时目录由 `FileStorage` 自动创建
- **文件即契约**：所有配置文件都有 `schema_version` 字段，变更通过 `VersionManager` 管理
- **人类可读**：知识条目使用 markdown + YAML front matter，可直接用编辑器阅读

#### 测试约定

- **测试目录结构**与源码模块一一对应：`tests/runtime/`、`tests/storage/`、`tests/knowledge/`、`tests/adapter/`、`tests/tools/`、`tests/platform/`
- **测试文件命名**：`test_<module_name>.py`，如 `test_session_manager.py`、`test_knowledge_store.py`
- **测试类命名**：`Test*`，如 `TestSessionManager`、`TestKnowledgeStore`
- **每个测试使用 `tmp_path` fixture** 创建临时 `.garage/` 目录，不污染项目状态
- **集成测试**放在 `tests/integration/`，如 `test_e2e_workflow.py`
- **安全测试**放在 `tests/security/`
- **兼容性测试**放在 `tests/compatibility/`
- 当前共 **860 个测试**，全部通过
- 运行测试：`uv run pytest tests/ -q`（快速模式）或 `uv run pytest tests/ -v`（详细模式）

# garage-agent

**English** | [中文](README.zh-CN.md)

<p align="center">
  <a href="https://github.com/hujianbest/garage-agent/actions/workflows/test.yml"><img src="https://github.com/hujianbest/garage-agent/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License: Apache 2.0"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://github.com/hujianbest/garage-agent/releases/tag/v0.1.0"><img src="https://img.shields.io/badge/release-v0.1.0-orange.svg" alt="Release v0.1.0"></a>
  <a href="CODE_OF_CONDUCT.md"><img src="https://img.shields.io/badge/code%20of%20conduct-Contributor%20Covenant-ff69b4.svg" alt="Code of Conduct"></a>
</p>

> **A local-first home for your agent's skills, knowledge, and experience.**
> Use it with Claude Code, Cursor, or OpenCode — your data stays in your repo, your skills follow you across hosts, and the system gets a little sharper every time you ship something.

`garage-agent` is built for **solo creators** who refuse to choose between "stuck in one IDE forever" and "starting from scratch every conversation". It treats your agent capability as something you grow over time — sessions become memories, memories become skills, skills become packs, and packs travel with you.

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│   sessions  ─►  knowledge + experience  ─►  skills + packs   │
│       ▲                    │                       │         │
│       │                    ▼                       ▼         │
│       └──── host context ◄──── garage sync ◄─── publish      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Why garage-agent

| | Without garage-agent | With garage-agent |
|---|---|---|
| **Your data** | Locked inside one host's session DB | Plain files under `.garage/` in your own repo |
| **Switching hosts** | Re-teach everything from scratch | One `garage init --hosts <new-host>` and your skills + memory follow |
| **What you've learned** | Disappears when the conversation ends | Auto-extracted into `knowledge/` and `experience/`, reviewed by you |
| **Sharing capability** | Copy-paste prompts into a Notion page | `garage pack publish --to <git-url>` with anonymization + provenance |
| **The garage promise** | A black box with a chat field | A workshop you can read, modify, and pass on |

## Features

- **Local-first by design** — Every session, knowledge entry, and experience record lives in `.garage/` as a readable Markdown / JSON / YAML file. Stop using garage-agent tomorrow and your data still opens in any text editor.
- **Three first-class hosts** — Claude Code, Cursor, OpenCode. Same pack, same skills, same memory — `garage init --hosts claude,cursor,opencode --yes` materializes everything into each host's native directory.
- **A complete memory loop** — `garage sync` pushes your top knowledge + recent experience into each host's context surface (`CLAUDE.md`, `.cursor/rules/`, `.opencode/AGENTS.md`); `garage session import --from <host>` pulls host conversation history back for extraction.
- **Skill packs that travel** — 5 packs ship in v0.1.0 (`garage` / `coding` / `writing` / `search` / `code-audit`) with **42 skills + 5 agents** (3 onboarding agents in `garage` + 2 code-audit agents). Install third-party packs from any git URL; publish your own with `garage pack publish`.
- **The system suggests its own next skill** — When the same `(problem_domain, tag)` pattern shows up in 5+ sessions, `garage skill suggest` proposes a SKILL.md draft. `garage skill promote` turns it into a real pack skill.
- **Workflow recall** — `garage recall workflow --problem-domain cli-design` returns the skill chains that have actually worked for similar past tasks, ranked by frequency.
- **Privacy-respecting share** — `garage pack publish` runs a sensitive-pattern scan before pushing; `garage knowledge export --anonymize` lets you share what you've learned without leaking secrets.
- **Human-in-charge** — Destructive and shareable operations are explicit (`--yes` / `--force` / `--anonymize`). The system suggests; you decide.

## What's in the box (v0.1.0)

| Pack | Version | Skills | Agents | Purpose |
|---|---|---|---|---|
| `packs/garage/` | 0.3.0 | 3 | 3 | Onboarding (`garage-hello` / `find-skills` / `writing-skills`) + production agents (`code-review-agent` / `blog-writing-agent` / `garage-sample-agent`) |
| `packs/coding/` | 0.5.0 | 29 | 0 | The full HarnessFlow engineering workflow (spec → design → tasks → TDD → review → finalize), reverse-synced from `harness-flow` main (v0.6.0-aligned) |
| `packs/writing/` | 0.2.0 | 5 | 0 | `blog-writing` / `humanizer-zh` / `hv-analysis` / `khazix-writer` / `magazine-web-ppt` |
| `packs/search/` | 0.1.0 | 1 | 0 | `ai-weekly` (X/Twitter weekly curation in Chinese) |
| `packs/code-audit/` | 0.1.0 | 4 | 2 | Existing-code bug audit (`audit-planner` / `audit-reviewer` / `audit-verifier` / `audit-reporter`) + two-stage agents |

`garage init --hosts all` materializes **126 skill files + 10 agent files** (42 skills × 3 hosts; agents to claude + opencode only — Cursor has no agent surface yet).

## Install

`garage-agent` requires Python 3.11+ and `uv` (recommended) or `pip`.

```bash
# clone + install in an isolated uv-managed venv (recommended)
git clone https://github.com/hujianbest/garage-agent.git
cd garage-agent
uv sync
uv run garage --help

# or, pip-style editable install from a clone
pip install -e .

# PyPI (once published — see release notes for status)
pip install garage-agent
```

> The PyPI distribution name is **`garage-agent`** (`pip install garage-agent`) but the Python import path is **`garage_os`** (`import garage_os`). Same pattern as Pillow / `import PIL`.

## Quick Start (60 seconds)

```bash
# 1) materialize all 4 packs into Claude Code + Cursor + OpenCode
garage init --hosts claude,cursor,opencode --yes

# 2) check what landed
garage status

# 3) push your top knowledge + recent experience into each host's context surface
garage sync --hosts claude,cursor,opencode

# 4) (after a few sessions) pull host history back for memory extraction
garage session import --from claude --all

# 5) ask: which workflow paths have worked for similar problems?
garage recall workflow --problem-domain cli-design

# 6) and: did the system spot any patterns worth turning into skills?
garage skill suggest --rescan
```

That's it — open Claude Code, Cursor, or OpenCode in the same directory and the skills + memory are already there.

## How the flywheel works

1. **You work.** Conversations happen in your host of choice. Garage's `session import` reads them back.
2. **The system extracts.** Repeated patterns and decisions become candidate `knowledge/` entries (decisions / patterns / solutions / style) and `experience/` records.
3. **You review.** Nothing enters long-term memory without `garage memory review`. The user-pact is explicit: the human keeps the steering wheel.
4. **The system pushes back.** `garage sync` writes your top-N knowledge into `CLAUDE.md` / `.cursor/rules/garage-context.mdc` / `.opencode/AGENTS.md`, so the next conversation starts already knowing what you know.
5. **Patterns become skills.** When 5+ sessions hit the same `(problem_domain, tag)` cluster, `garage skill suggest` proposes a draft. You review, refine via `hf-test-driven-dev`, and `garage skill promote` it into a pack.
6. **Skills become shareable.** `garage pack publish --to <git-url>` ships your pack with sensitive-pattern scan and force-push prompt. Other people `garage pack install <git-url>` to pull it.

## Pack lifecycle

```bash
# install someone else's pack from any git URL
garage pack install https://github.com/<user>/<their-pack>.git

# list installed packs (shows source_url for installed-from-URL packs)
garage pack ls

# update from source_url
garage pack update <pack-id> --yes

# publish (sensitive-pattern scan + force-push prompt + 7 anonymization rules)
garage pack publish <pack-id> --to https://github.com/<you>/<pack-name>.git --yes

# clean uninstall (reverse-installs from every host directory)
garage pack uninstall <pack-id> --yes

# share what you've learned, anonymized
garage knowledge export --anonymize
```

## CLI reference (top-level)

| Command | Purpose |
|---|---|
| `garage init` | Initialize Garage in this project + materialize packs into hosts |
| `garage status` | Show what's installed, what's pending review, what's stale |
| `garage run <skill>` | Execute a skill via the configured host adapter |
| `garage sync` | Push top-N memory into host context surfaces |
| `garage session import` | Pull host conversation history back for extraction |
| `garage memory review` | Approve / reject extracted knowledge candidates |
| `garage knowledge add` / `knowledge edit` / `knowledge show` / `knowledge delete` | Author and curate knowledge entries |
| `garage knowledge search` / `knowledge list` / `knowledge link` / `knowledge graph` | Recall, list, and link knowledge entries (F006 graph) |
| `garage knowledge export` | Anonymized tarball export |
| `garage experience add` / `experience show` / `experience delete` | Author experience records |
| `garage pack install` / `pack ls` / `pack uninstall` / `pack update` / `pack publish` | Full pack lifecycle |
| `garage skill suggest` | List system-proposed skill drafts |
| `garage skill promote` | Promote a draft into a pack |
| `garage recall workflow` | Recommend skill chains based on historical experience |
| `garage recommend` | Recommend knowledge entries for the current task |

Run any command with `--help` for full options.

## Documentation

| Section | What you'll find |
|---|---|
| [User Guide](docs/guides/garage-agent-user-guide.md) | End-to-end walkthrough of every command, with worked examples |
| [Soul docs](docs/soul/) | The **why**: [`manifesto.md`](docs/soul/manifesto.md), [`user-pact.md`](docs/soul/user-pact.md), [`design-principles.md`](docs/soul/design-principles.md), [`growth-strategy.md`](docs/soul/growth-strategy.md) |
| [Skill anatomy](docs/principles/skill-anatomy.md) | Mandatory reading before authoring or rewriting any skill |
| [Pack contracts](packs/README.md) | `pack.json` schema, directory layout, host installer behavior |
| [Feature specs](docs/features/) | F001–F014 specs (the "what was built" record) |
| [Release notes](RELEASE_NOTES.md) | Per-cycle user-visible changes |
| [Contributing](CONTRIBUTING.md) | AHE / HF workflow, dev setup, PR checklist, file touch boundaries |
| [Security](SECURITY.md) | Vulnerability reporting via GitHub Security Advisory |

## Repository map

| Path | Purpose |
|---|---|
| [`packs/`](packs/) | Distributable packs (single source of truth) |
| [`src/garage_os/`](src/garage_os/) | Python runtime: types, storage, runtime, knowledge, adapter (host installer + sync), tools, platform |
| [`.garage/`](.garage/) | Workspace runtime state (sessions, knowledge, experience, manifests, contracts, config) |
| [`docs/`](docs/) | Soul docs, specs, designs, reviews, approvals, guides, principles |
| [`tests/`](tests/) | ~1045 tests mirroring `src/garage_os/` module layout |
| [`AGENTS.md`](AGENTS.md) | Agent-facing conventions + dev notes |
| [`RELEASE_NOTES.md`](RELEASE_NOTES.md) | F001 → F014 per-cycle change log |

## Roadmap

v0.1.0 closes 14 delivery cycles (F001–F014). Snapshot of where we are vs. the manifesto:

```
Belief 1  Data is yours       █████████████████████████████████  5/5  ✅
Belief 2  Host portability    █████████████████████████          4/5  ⚠️ 4th host still requires source edit
Belief 3  Progressive enhance █████████████████████████████████  5/5  ✅
Belief 4  Human + machine     █████████████████████████████████  5/5  ✅ flywheel closed
Belief 5  Shareable           █████████████████████████████████  5/5  ✅ install / update / publish / anonymize

Stage 1  Toolbox     ████████████████████  100%
Stage 2  Memory      ████████████████████  100%
Stage 3  Craftsman   █████████████          65%   ← skill mining shipped, manual refinement still required
Stage 4  Ecosystem   ████████               40%   ← lifecycle complete; signature + discovery still pending
```

**v0.2 candidates** (in priority order):

1. Real 3-way merge for `pack update --preserve-local-edits`
2. Pluggable host registry (drop the source-edit requirement for a 4th host)
3. Pack signature / GPG + `garage pack search` central discovery
4. Cross-machine `garage sync` with git-aware merging
5. `ruff` + `mypy` cleanup → re-add as blocking CI jobs
6. Cursor session history reader (currently a stub)

See [`docs/planning/`](docs/planning/) for full gap analysis.

## A note on the name

A garage is where things start before they're polished — close to the work, shaped by iteration, able to grow into something real without losing its identity along the way. `garage-agent` is the place where your agent capability can be **built by hand**, **compounded over time**, and eventually **leave the garage** without being thrown away.

It's deliberately not a SaaS product, not a single-host wrapper, not a generic all-in-one framework, and not full autopilot. It's a workshop.

## Contributing

The most useful contributions right now: workflow quality, host portability, docs clarity, runtime hardening, and real-world examples.

- Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a non-trivial PR
- For substantive changes, follow the AHE / HF workflow that this repo dogfoods (`docs/features/Fxxx-*.md` spec → `docs/designs/` design → `docs/tasks/` tasks → implementation + tests → `docs/reviews/` self-review → `docs/approvals/` finalize)
- Be kind. The [Code of Conduct](CODE_OF_CONDUCT.md) is the Contributor Covenant 2.1.
- Security issues: please **don't** open public issues — see [`SECURITY.md`](SECURITY.md).

## License

[Apache License 2.0](LICENSE). Chosen for the explicit patent grant and downstream-friendliness — aligned with the manifesto's "your data, your skills, your right to share them" stance.

## Acknowledgments

`garage-agent` stands on the shoulders of the open-source agent community. The HarnessFlow workflow chain in `packs/coding/` reverse-syncs from [`hujianbest/harness-flow`](https://github.com/hujianbest/harness-flow). Design influences are documented honestly in [`docs/wiki/`](docs/wiki/), including comparative analysis of Hermes Agent, OpenSpec, gstack, get-shit-done, longtaskforagent, and Superpowers.

Built for everyone who wanted their agent to **remember last month**, **know their style**, and **come with them when they switch tools**.

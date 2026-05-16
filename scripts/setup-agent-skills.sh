#!/usr/bin/env bash
# scripts/setup-agent-skills.sh
#
# Regenerate .agents/skills/ symlinks pointing into packs/<pack-id>/skills/<skill>.
# Run once after a fresh clone (or whenever a skill is added/renamed under packs/).
# See .agents/README.md for the rationale.
#
# Idempotent: removes any existing .agents/skills/ tree first, then rebuilds.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d "packs" ]; then
  echo "ERROR: packs/ directory not found; this script must run from the repo root" >&2
  exit 1
fi

# Wipe and recreate
rm -rf .agents/skills
mkdir -p .agents/skills

# 28 hf-* + using-hf-workflow → packs/coding/skills/
CODING_SKILLS=(
  hf-browser-testing hf-code-review hf-completion-gate hf-context-mesh hf-design
  hf-design-review hf-discovery-review hf-doc-freshness-gate hf-experiment hf-finalize
  hf-gap-analyzer hf-hotfix hf-increment hf-product-discovery hf-regression-gate
  hf-release hf-spec-review hf-specify hf-tasks hf-tasks-review hf-test-driven-dev
  hf-test-review hf-traceability-review hf-ui-design hf-ui-review hf-ultrawork
  hf-wisdom-notebook hf-workflow-router using-hf-workflow
)
for s in "${CODING_SKILLS[@]}"; do
  if [ -d "packs/coding/skills/$s" ]; then
    ln -sf "../../packs/coding/skills/$s" ".agents/skills/$s"
  else
    echo "WARN: packs/coding/skills/$s missing; skipping" >&2
  fi
done

# code-audit pack (Slice A)
CODE_AUDIT_SKILLS=(audit-planner audit-reporter audit-reviewer audit-verifier)
for s in "${CODE_AUDIT_SKILLS[@]}"; do
  if [ -d "packs/code-audit/skills/$s" ]; then
    ln -sf "../../packs/code-audit/skills/$s" ".agents/skills/$s"
  else
    echo "WARN: packs/code-audit/skills/$s missing; skipping" >&2
  fi
done

# Garage common skills
GARAGE_SKILLS=(find-skills writing-skills)
for s in "${GARAGE_SKILLS[@]}"; do
  if [ -d "packs/garage/skills/$s" ]; then
    ln -sf "../../packs/garage/skills/$s" ".agents/skills/$s"
  else
    echo "WARN: packs/garage/skills/$s missing; skipping" >&2
  fi
done

# Writing pack skills under .agents/skills/write-blog/
mkdir -p .agents/skills/write-blog
WRITING_SKILLS=(blog-writing humanizer-zh hv-analysis khazix-writer)
for s in "${WRITING_SKILLS[@]}"; do
  if [ -d "packs/writing/skills/$s" ]; then
    ln -sf "../../../packs/writing/skills/$s" ".agents/skills/write-blog/$s"
  else
    echo "WARN: packs/writing/skills/$s missing; skipping" >&2
  fi
done

echo "✓ Regenerated $(find .agents/skills -maxdepth 2 -type l | wc -l) skill symlinks under .agents/skills/"

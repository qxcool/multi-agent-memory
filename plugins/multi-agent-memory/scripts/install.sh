#!/usr/bin/env bash
# Install multi-agent-memory CLI + symlink Skill into host skill directories.
set -euo pipefail

HOSTS="${HOSTS:-claude,cursor,deepseek,opencode}"
SKIP_PIP=0
PROJECT_AGENTS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hosts)
      HOSTS="$2"
      shift 2
      ;;
    --skip-pip)
      SKIP_PIP=1
      shift
      ;;
    --project-agents)
      PROJECT_AGENTS=1
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--hosts claude,cursor,deepseek,opencode,codex] [--skip-pip] [--project-agents]"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_SRC="$PLUGIN_ROOT/skills/multi-agent-memory"
REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"

if [[ ! -f "$SKILL_SRC/SKILL.md" ]]; then
  echo "Skill not found: $SKILL_SRC" >&2
  exit 1
fi

link_skill() {
  local dst="$1"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" || -L "$dst" ]]; then
    rm -rf "$dst"
  fi
  if ln -s "$SKILL_SRC" "$dst" 2>/dev/null; then
    echo "linked $dst"
  else
    echo "symlink failed; copying to $dst"
    cp -R "$SKILL_SRC" "$dst"
  fi
}

if [[ "$SKIP_PIP" -eq 0 ]]; then
  echo "Installing Python package from $PLUGIN_ROOT ..."
  python3 -m pip install --upgrade "$PLUGIN_ROOT"
fi

IFS=',' read -r -a HOST_ARR <<< "$HOSTS"
for raw in "${HOST_ARR[@]}"; do
  h="$(echo "$raw" | tr '[:upper:]' '[:lower:]' | xargs)"
  case "$h" in
    claude)
      link_skill "${HOME}/.claude/skills/multi-agent-memory"
      ;;
    cursor)
      link_skill "${HOME}/.cursor/skills/multi-agent-memory"
      ;;
    deepseek)
      link_skill "${HOME}/.agents/skills/multi-agent-memory"
      ;;
    opencode)
      link_skill "${HOME}/.agents/skills/multi-agent-memory"
      link_skill "${HOME}/.opencode/skills/multi-agent-memory"
      ;;
    codex)
      echo "Codex: use marketplace (codex plugin add multi-agent-memory@multi-agent-memory); Skill ships in plugin."
      ;;
    "")
      ;;
    *)
      echo "Unknown host '$h'" >&2
      ;;
  esac
done

if [[ "$PROJECT_AGENTS" -eq 1 ]]; then
  link_skill "$REPO_ROOT/.agents/skills/multi-agent-memory"
fi

echo
echo "Done. Verify:"
echo "  python3 -c 'import multi_agent_memory as m; print(m.__version__)'"
echo "  memory-hub doctor"
echo "Agent short names: claude | codex | cursor | deepseek | opencode"
echo "Adapters: $PLUGIN_ROOT/adapters/README.md"

#!/usr/bin/env bash
# cc-token-audit — install + enable ONE context-saving tool for the passive A/B.
# Lazy by design: install only the tool you're testing, not all three.
# Idempotent: skips what's already present. $0 (no API calls; only package/plugin installs).
#
#   setup_tool.sh --check                 # report what's installed/enabled, change nothing
#   setup_tool.sh context-mode            # install + enable context-mode (the usual #1 pick)
#   setup_tool.sh ponytail
#   setup_tool.sh rtk
#   setup_tool.sh codebase-memory-mcp               # code-graph MCP (fewer file-discovery reads)
#   setup_tool.sh token-savior            # all-in-one MCP: indexing + bash compaction + memory
#   setup_tool.sh <tool> --disable        # turn a tool back off after the test
set -uo pipefail

CM_REPO="mksglu/context-mode"          # context-mode marketplace (GitHub)
PONY_REPO="DietrichGebert/ponytail"    # ponytail marketplace (GitHub)

have() { command -v "$1" >/dev/null 2>&1; }
note() { printf '  %s\n' "$*"; }

preflight() {
  local miss=0
  have claude || { note "MISSING: claude CLI (required for plugin tools)"; miss=1; }
  have node   || note "WARN: node not found — context-mode & ponytail need Node.js (>=18)."
  have git    || note "WARN: git not found — marketplace add from GitHub needs git."
  return $miss
}

check() {
  echo "== cc-token-audit tool availability =="
  have rtk && note "rtk: installed ($(rtk --version 2>/dev/null))" || note "rtk: NOT installed (brew install rtk)"
  have codebase-memory-mcp && note "codebase-memory-mcp: installed ($(codebase-memory-mcp --version 2>/dev/null))" || note "codebase-memory-mcp: NOT installed (curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash)"
  have token-savior && note "token-savior: installed" || note "token-savior: NOT installed (pip install 'token-savior-recall[mcp]')"
  have cozempic && note "cozempic: installed" || note "cozempic: NOT installed (pip install cozempic, or /plugin marketplace add Ruya-AI/cozempic)"
  echo "  -- claude plugins --"
  claude plugin list 2>/dev/null | grep -iE 'context-mode|ponytail|cozempic' || note "(none of context-mode/ponytail/cozempic installed)"
  echo "  -- claude MCP servers --"
  claude mcp list 2>/dev/null | grep -iE 'codebase-memory-mcp|token-savior' || note "(no codebase-memory-mcp/token-savior MCP registered)"
  echo "  -- ccusage (the measurement instrument) --"
  have ccusage && note "ccusage: installed" || { have npx && note "ccusage: via npx (ok)"; } || note "ccusage: MISSING (npm i -g ccusage)"
}

ensure_marketplace() { # repo
  local repo="$1" name="${1##*/}"
  if claude plugin marketplace list 2>/dev/null | grep -qi "$name"; then
    note "marketplace '$name' already added"
  else
    note "adding marketplace $repo ..."; claude plugin marketplace add "$repo" || return 1
  fi
}

install_plugin() { # plugin-name repo
  local name="$1" repo="$2"
  ensure_marketplace "$repo" || { note "marketplace add failed for $repo"; return 1; }
  if claude plugin list 2>/dev/null | grep -qi "$name"; then note "$name already installed"; else
    note "installing $name ..."; claude plugin install "$name" || claude plugin install "${name}@${name}" || return 1
  fi
  note "enabling $name ..."; claude plugin enable "$name" 2>/dev/null
  note "DONE. Verify with: claude plugin list | grep $name"
}

TOOL="${1:-}"; ACTION="${2:-}"
case "$TOOL" in
  --check|"") check; exit 0 ;;
esac
preflight || { echo "Fix MISSING prerequisites above, then re-run."; exit 1; }

case "$TOOL" in
  rtk)
    if have rtk; then note "rtk already installed ($(rtk --version 2>/dev/null))"; else
      if have brew; then note "brew install rtk ..."; brew install rtk || exit 1
      elif have cargo; then note "cargo install rtk ..."; cargo install rtk || exit 1
      else note "Need Homebrew or cargo to install rtk. See https://www.rtk-ai.app/"; exit 1; fi
    fi
    if [ "$ACTION" = "--disable" ]; then note "rtk has no global hook to remove unless you ran 'rtk init -g'; remove its block from ~/.claude/CLAUDE.md / project CLAUDE.md."; exit 0; fi
    note "enabling global rtk hook: rtk init -g"; rtk init -g
    ;;
  context-mode)
    [ "$ACTION" = "--disable" ] && { claude plugin disable context-mode; note "context-mode disabled."; exit 0; }
    install_plugin context-mode "$CM_REPO" ;;
  ponytail)
    [ "$ACTION" = "--disable" ] && { claude plugin disable ponytail; note "ponytail disabled."; exit 0; }
    install_plugin ponytail "$PONY_REPO" ;;
  codebase-memory-mcp)
    # Code-intelligence MCP: tree-sitter knowledge graph (158 langs + Hybrid LSP),
    # cross-repo edges, sub-ms structural queries. Static binary (no Node.js/npm).
    # The binary's `install` respects CLAUDE_CONFIG_DIR if the user set it (forks).
    if [ "$ACTION" = "--disable" ]; then
      note "uninstalling codebase-memory-mcp agent config ..."; codebase-memory-mcp uninstall -y 2>/dev/null
      note "config removed (binary stays at ~/.local/bin; rm manually to fully remove)."; exit 0
    fi
    if have codebase-memory-mcp; then note "codebase-memory-mcp already installed ($(codebase-memory-mcp --version 2>/dev/null))"; else
      have curl || { note "Need curl to download codebase-memory-mcp."; exit 1; }
      note "installing binary via official install.sh (--skip-config → binary only) ..."
      curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash -s -- --skip-config || { note "binary install failed"; exit 1; }
    fi
    note "wiring into Claude Code: codebase-memory-mcp install -y (respects CLAUDE_CONFIG_DIR if set)"
    codebase-memory-mcp install -y || { note "agent config install failed — run 'codebase-memory-mcp install' manually"; exit 1; }
    note "In Claude: say \"Index this project\" (or the index_repository MCP tool) to build the graph."
    ;;
  cozempic)
    # Active context PRUNER (vs context-mode's read-only recall). Higher-risk:
    # mutates transcripts + reloads the Claude process. marketplace plugin route
    # auto-wires the SessionStart/PreCompact hooks + /cozempic:* skills.
    if [ "$ACTION" = "--disable" ]; then
      note "removing cozempic plugin ..."; claude plugin uninstall cozempic 2>/dev/null
      note "cozempic plugin removed (pip uninstall cozempic to fully remove the CLI)."; exit 0
    fi
    install_plugin "cozempic" "Ruya-AI/cozempic" || { note "cozempic plugin install failed — fallback: 'pip install cozempic' then 'cozempic init'"; exit 1; }
    note "Per repo: cozempic init  (builds guard config; SessionStart hook auto-starts the daemon)"
    note "CAUTION: cozempic reloads the Claude process at its hard tiers + mutates"
    note "         transcripts + auto-updates on SessionStart. On forks/non-stock configs,"
    note "         disable its auto-updater + reconcile thresholds with CLAUDE_CODE_* env first."
    ;;
  token-savior)
    if [ "$ACTION" = "--disable" ]; then
      note "removing token-savior MCP ..."; claude mcp remove token-savior 2>/dev/null
      note "token-savior MCP removed. Any bash hooks added by 'ts init' remain in your Claude settings — remove them there."; exit 0
    fi
    if have token-savior; then note "token-savior already installed"; else
      have pip3 || have pip || { note "Need python3/pip to install token-savior."; exit 1; }
      note "pip install token-savior-recall[mcp] ..."
      { have pip3 && pip3 install "token-savior-recall[mcp]"; } || pip install "token-savior-recall[mcp]" || exit 1
    fi
    ts_bin="$(command -v token-savior || true)"
    [ -z "$ts_bin" ] && { note "token-savior binary not on PATH after install — check your pip environment."; exit 1; }
    note "registering MCP: claude mcp add token-savior (profile=optimized) ..."
    claude mcp add token-savior -e TOKEN_SAVIOR_PROFILE=optimized -- "$ts_bin" 2>/dev/null \
      || claude mcp add token-savior -- "$ts_bin" \
      || { note "MCP add failed — register manually: claude mcp add token-savior -- $ts_bin"; }
    note "optional bash-output compaction hooks:  ts init --agent claude --yes"
    ;;
  *) echo "Unknown tool '$TOOL'. Use: context-mode | ponytail | rtk | codebase-memory-mcp | cozempic | token-savior | --check"; exit 1 ;;
esac

echo
note "Tool ready. Mark the A/B start:  python3 \"$(dirname "$0")/compare.py\" --enable $TOOL"
note "Then use Claude Code normally ~1-2 weeks and run compare.py to measure."

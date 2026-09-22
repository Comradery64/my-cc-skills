---
name: task-manager
description: CLI tool for managing on-disk Claude Code task lists outside of Claude Code's built-in tools. Use this skill when tasks need to be archived, bulk cleaned up, or when you need a high-level view of task dependencies. Triggers: (1) User asks to clean up or archive completed tasks, (2) Too many resolved tasks cluttering the list, (3) Need to visualize task dependencies, (4) Want to manage tasks via command line.
---

# Task Manager CLI

You have access to `cc-mirror-tasks` — a local CLI for managing the
on-disk JSON task files that `TaskCreate` writes under
`<CLAUDE_CONFIG_DIR>/tasks/<session_uuid>/<id>.json`.

**Note:** the upstream `cc-mirror` v2.1.0 npm package does NOT ship a `tasks`
subcommand (`npx cc-mirror tasks` returns the help screen). `cc-mirror-tasks`
is a local Python binary installed at `~/.local/bin/cc-mirror-tasks` that
fills the gap by operating directly on the JSON files. If it isn't present,
ask the user to reinstall it (the source previously lived in the user's
session memory; see the `reference_pty_runner_arch` memory for clau-decode
context if relevant).

## Auto-Detection

The CLI auto-detects your variant from:

1. Explicit `--variant <name>` (highest priority)
2. `$CLAUDE_CONFIG_DIR` env var
3. The sole installed variant under `~/.cc-mirror/` if there's only one

For multi-variant setups, pass `--variant` explicitly or `--all-variants`
to span all of them.

## Commands

```bash
# List tasks
cc-mirror-tasks                          # Open tasks (default; pending + in_progress)
cc-mirror-tasks list --status all        # All statuses
cc-mirror-tasks list --status completed  # Just completed
cc-mirror-tasks list --include-archive   # Include archived tasks
cc-mirror-tasks list --session <uuid>    # Filter to a specific session

# View dependencies
cc-mirror-tasks graph                    # Open-task dependency tree
cc-mirror-tasks graph --status all       # All-task dependency tree

# Archive completed tasks (moves to <session>/archive/, preserves history)
cc-mirror-tasks archive --resolved --dry-run    # Preview
cc-mirror-tasks archive --resolved              # Confirm at the prompt
cc-mirror-tasks archive --resolved --yes        # Skip confirm

# Delete completed tasks permanently (no history)
cc-mirror-tasks clean --resolved --dry-run      # Preview
cc-mirror-tasks clean --resolved                # Confirm at the prompt
cc-mirror-tasks clean --resolved --yes          # Skip confirm

# Single-task operations
cc-mirror-tasks show <id>                # Full task details
cc-mirror-tasks archive <id>             # Archive one task
cc-mirror-tasks clean <id>               # Delete one task
```

Glyphs in the list output: `○ pending`, `◐ in_progress`, `● completed`, `✗ deleted`.

## When to Use

Use `AskUserQuestion` to confirm with the user before bulk operations:

```
When tasks are cluttering:
  → "Archive resolved tasks?" (preserves in archive folder)
  → "Delete resolved tasks?" (permanent removal)
  → "Show task graph first?" (see dependencies)

When user wants to see other variants:
  → "Which variant?" (then use --variant flag)
  → "All variants?" (then use --all-variants flag)
```

## Viewing Other Variants

```bash
# Different variant
cc-mirror-tasks --variant zai

# All variants together
cc-mirror-tasks --all-variants
cc-mirror-tasks --all-variants list --status all
```

## Archive vs Clean

| Action  | Command              | Effect                                                  |
| ------- | -------------------- | ------------------------------------------------------- |
| Archive | `archive --resolved` | Moves to `<session>/archive/` (collision-safe rename)   |
| Clean   | `clean --resolved`   | Permanently removes the JSON files                      |

**Prefer archive** — it preserves task history for future reference.

## Caveats

- Task IDs are session-scoped (each session starts from 1). `graph`
  treats same-numbered tasks across sessions as the same node; in
  multi-session views this surfaces as `↺ (cycle)` markers. Use
  `--session <uuid>` for a clean per-session graph.
- `--team` (which the prior version of this skill advertised) is NOT
  implemented yet — the on-disk task JSON has no team field. Filtering
  by team would require cross-referencing each session's JSONL to find
  its cwd, then matching against git root. If you need this, ask the
  user to surface it as a polish item.

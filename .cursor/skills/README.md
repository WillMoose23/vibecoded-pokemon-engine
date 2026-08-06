# Cursor skills backup

Project-specific and shared Cursor **skills** (`SKILL.md` per folder) live here for git backup on `development`.

## Sources

| Location | Role |
|----------|------|
| `.cursor/skills/` (this repo) | Version-controlled backup |
| `~/.cursor/skills/` | Global user skills (synced in) |
| Project-only skills | e.g. `event-script-opcode-docs`, `planning-rule` — edit here or under project `.cursor/skills/` |

## Sync before push

```bash
python3 docs/cursor_helper_scripts/sync_cursor_backup.py
```

Runs plan + skill sync. Required by **Git-Push-Development-Rule** before every push to `development`.

## Restore on another machine

```bash
cp -R .cursor/skills/* ~/.cursor/skills/
```

Create `~/.cursor/skills/` first if needed.

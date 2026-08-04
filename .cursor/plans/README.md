# Cursor plans backup

This directory is the **version-controlled backup** of Cursor plan files (`*.plan.md`).

## Source

Plans are authored in the global Cursor plans folder:

`~/.cursor/plans/`

Before every push to `development`, run:

```bash
python3 tools/sync_cursor_plans.py
```

Or ask Cursor to **push to GitHub** — the Git-Push-Development-Rule runs sync automatically.

## Restore

After cloning or pulling on another machine, plans in this folder are available in the repo. Copy into `~/.cursor/plans/` if you need them in the Cursor UI:

```bash
cp .cursor/plans/*.plan.md ~/.cursor/plans/
```

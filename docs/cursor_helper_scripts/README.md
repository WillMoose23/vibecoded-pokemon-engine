# Cursor helper scripts

Python utilities for **Cursor IDE workflow** (plan/skill backup, doc PDF generation). These are **not** part of the game runtime, event editor, or map editor application code.

| Script | Purpose |
|--------|---------|
| `sync_cursor_plans.py` | Copy `~/.cursor/plans/*.plan.md` → `.cursor/plans/` |
| `sync_cursor_skills.py` | Copy `~/.cursor/skills/*` → `.cursor/skills/` |
| `sync_cursor_backup.py` | Run plan + skill sync (used before git push) |
| `generate_github_guide_pdf.py` | Build `docs/github-and-setup-guide.pdf` |

Run from repo root:

```bash
python3 docs/cursor_helper_scripts/sync_cursor_backup.py
python3 docs/cursor_helper_scripts/generate_github_guide_pdf.py
```

Documented in `docs/tools_doc.md` under each script’s `TOOL:` entry.

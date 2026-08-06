#!/usr/bin/env python3
"""Generate docs/github-and-setup-guide.pdf from the project Git + setup guide."""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[2]
OUT_PDF = ROOT / "docs" / "github-and-setup-guide.pdf"
REPO_URL = "https://github.com/WillMoose23/vibecoded-pokemon-engine.git"


class GuidePDF(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def _write_block(self, text: str, h: float = 5) -> None:
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, h, text)

    def h1(self, text: str) -> None:
        self.ln(4)
        self.set_font("Helvetica", "B", 16)
        self._write_block(text, 8)
        self.ln(2)

    def h2(self, text: str) -> None:
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self._write_block(text, 7)
        self.ln(1)

    def h3(self, text: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self._write_block(text, 6)
        self.ln(1)

    def body(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self._write_block(text, 5)
        self.ln(1)

    def bullet(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self._write_block(f"  - {text}", 5)

    def code_block(self, text: str) -> None:
        self.set_font("Courier", "", 9)
        self.set_fill_color(245, 245, 245)
        for line in text.strip().splitlines():
            self.set_x(self.l_margin)
            self.cell(self.epw, 5, "  " + line, ln=True, fill=True)
        self.ln(2)

    def term(self, name: str, definition: str) -> None:
        self.set_font("Helvetica", "B", 10)
        self._write_block(name, 5)
        self.set_font("Helvetica", "", 10)
        self._write_block(definition, 5)
        self.ln(1)


def build(pdf: GuidePDF) -> None:
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.alias_nb_pages()

    pdf.h1("Git, GitHub & Environment Setup Guide")
    pdf.body(
        "vibecoded-pokemon-engine - step-by-step reference for cloning, building, "
        "testing, and working with Git branches on this project."
    )
    pdf.body(f"Repository: {REPO_URL}")

    # --- Glossary ---
    pdf.h1("Part 1 - Definitions (Glossary)")
    terms = [
        (
            "Git",
            "Version control on your computer. Tracks file changes, branches, and history.",
        ),
        (
            "GitHub",
            "Cloud hosting for Git repositories. The remote named origin points here.",
        ),
        (
            "Repository (repo)",
            "The project folder plus its full Git history.",
        ),
        (
            "Remote",
            "A named link to a copy of the repo on another machine. origin is GitHub.",
        ),
        (
            "Branch",
            "An independent line of work. main and development can differ until merged.",
        ),
        (
            "Commit",
            "A saved snapshot of your changes with a message describing why.",
        ),
        (
            "Push",
            "Upload local commits to GitHub (origin).",
        ),
        (
            "Pull",
            "Download commits from GitHub and merge them into your current branch.",
        ),
        (
            "Fetch",
            "Download remote updates without merging yet. Safe preview of what changed.",
        ),
        (
            "Merge",
            "Combine another branch into your current branch (or on GitHub via Pull Request).",
        ),
        (
            "Pull Request (PR)",
            "GitHub UI to review and merge one branch into another (e.g. development into main).",
        ),
        (
            "Staging (git add)",
            "Mark which changed files will be included in the next commit.",
        ),
        (
            "Working tree",
            "Your live files on disk. Uncommitted edits live here.",
        ),
        (
            "HEAD",
            "The commit your current branch points to - your checked-out snapshot.",
        ),
        (
            "Tracking branch",
            "Local branch linked to a remote branch (e.g. development tracks origin/development).",
        ),
        (
            "Stash",
            "Temporarily shelve uncommitted changes so you can switch branches cleanly.",
        ),
        (
            "Reset",
            "Move HEAD (and optionally files) to an older commit. Can discard local work.",
        ),
        (
            "Force push",
            "Overwrite remote history. Dangerous on shared branches - avoid on main/development.",
        ),
        (
            "Merge conflict",
            "Git cannot auto-combine two edits to the same lines. You must resolve manually.",
        ),
    ]
    for name, definition in terms:
        pdf.term(name, definition)

    # --- Branch model ---
    pdf.add_page()
    pdf.h1("Part 2 - Branch Model for This Project")
    pdf.body("Use these branches consistently:")
    pdf.bullet("main - stable/production baseline. Merge-only from development via GitHub PR.")
    pdf.bullet("development - daily integration branch. Commit and push work here.")
    pdf.bullet(
        "development-local-ai - optional sandbox for local AI / experimental work. "
        "Safe to reset without affecting main or development."
    )
    pdf.ln(2)
    pdf.body("Typical flow:")
    pdf.code_block(
        """1. Work on development (or development-local-ai for experiments)
2. Commit + push to your branch
3. Open a Pull Request: development into main on GitHub
4. Review and merge when ready"""
    )
    pdf.body("Never push directly to main unless you explicitly intend to and understand the risk.")

    # --- Fresh setup ---
    pdf.h1("Part 3 - Fresh Environment Setup (After Clone)")
    pdf.h2("3.1 Prerequisites (macOS)")
    pdf.bullet("Xcode Command Line Tools: xcode-select --install")
    pdf.bullet("Homebrew: https://brew.sh")
    pdf.bullet("Git (usually included with Xcode CLT)")
    pdf.bullet("Python 3.9+ (macOS includes python3)")
    pdf.ln(1)
    pdf.h2("3.2 Clone the repository")
    pdf.code_block(
        f"""cd ~/Desktop   # or your projects folder
git clone {REPO_URL}
cd vibecoded-pokemon-engine
git fetch origin
git checkout development
git pull origin development --no-rebase"""
    )
    pdf.h2("3.3 Install build dependencies (C++ game + SDL)")
    pdf.code_block(
        """brew install sdl2 sdl2_ttf sdl2_image sdl2_mixer pkg-config"""
    )
    pdf.body("sdl2_mixer is optional; the Makefile enables audio when the library is present.")
    pdf.h2("3.4 Install Python tools (map editor)")
    pdf.code_block(
        """python3 -m pip install --user pygame
# Optional: generate this PDF
python3 -m pip install --user fpdf2"""
    )
    pdf.h2("3.5 Build and run the game")
    pdf.code_block(
        """make
make run"""
    )
    pdf.h2("3.6 Run tests (required before pushing)")
    pdf.code_block(
        """make test
python3 -m unittest discover -s tests -q"""
    )
    pdf.h2("3.7 Run the map editor (optional)")
    pdf.code_block(
        """python3 tools/map_editor.py"""
    )
    pdf.body("Run from the repository root. Requires pygame.")
    pdf.h2("3.8 Optional: GitHub CLI")
    pdf.code_block(
        """brew install gh
gh auth login"""
    )
    pdf.body("Use gh pr create to open Pull Requests from the terminal.")

    # --- Daily git ---
    pdf.add_page()
    pdf.h1("Part 4 - Daily Git Commands")
    pdf.h2("4.1 Check status (always start here)")
    pdf.code_block(
        """cd /path/to/vibecoded-pokemon-engine
git status
git branch -vv
git remote -v"""
    )
    pdf.h2("4.2 Pull latest (default: development)")
    pdf.code_block(
        """git fetch origin
git checkout development
git pull origin development --no-rebase"""
    )
    pdf.body("If you have uncommitted changes, commit or git stash before pulling.")
    pdf.h2("4.3 Create a new branch")
    pdf.code_block(
        """git checkout development
git pull origin development --no-rebase
git checkout -b my-feature-branch"""
    )
    pdf.body("Push the new branch the first time:")
    pdf.code_block("git push -u origin my-feature-branch")
    pdf.h2("4.4 Switch branches")
    pdf.code_block(
        """git checkout development
# or
git switch development"""
    )
    pdf.h2("4.5 Stage and commit")
    pdf.code_block(
        """git add path/to/file1 path/to/file2
git status
git commit -m "Short reason for the change in 1-2 sentences."
"""
    )
    pdf.body("Stage everything (use carefully):")
    pdf.code_block("git add -A")
    pdf.h2("4.6 Push")
    pdf.code_block(
        """git checkout development
git push origin development"""
    )
    pdf.body("First push on a new branch:")
    pdf.code_block("git push -u origin branch-name")

    pdf.h2("4.7 Stash uncommitted work")
    pdf.code_block(
        """git stash push -m "wip before pull"
git pull origin development --no-rebase
git stash pop"""
    )

    # --- Merge & PR ---
    pdf.add_page()
    pdf.h1("Part 5 - Merge & Pull Requests")
    pdf.h2("5.1 Merge on GitHub (recommended for main)")
    pdf.body("1. Push development to origin.")
    pdf.body("2. Open: https://github.com/WillMoose23/vibecoded-pokemon-engine/compare/main...development")
    pdf.body("3. Create Pull Request, review, merge.")
    pdf.h2("5.2 Merge locally (use with care)")
    pdf.code_block(
        """git checkout development
git pull origin development --no-rebase
git checkout main
git pull origin main --no-rebase
git merge development
git push origin main"""
    )
    pdf.body("Prefer GitHub PRs for merging into main so you get review and CI checks.")
    pdf.h2("5.3 Create PR with GitHub CLI")
    pdf.code_block(
        """git push -u origin development
gh pr create --base main --head development \\
  --title "Release: summary" \\
  --body "What changed and how to test."
"""
    )

    # --- Reset & rollback ---
    pdf.h1("Part 6 - Reset, Rollback & Recovery")
    pdf.h2("6.1 Discard uncommitted changes in one file")
    pdf.code_block("git restore path/to/file")
    pdf.h2("6.2 Discard ALL uncommitted changes (destructive)")
    pdf.code_block(
        """git restore .
git clean -fd   # removes untracked files - irreversible"""
    )
    pdf.h2("6.3 Undo last commit, keep file changes")
    pdf.code_block("git reset --soft HEAD~1")
    pdf.h2("6.4 Move branch back one commit, discard changes (destructive)")
    pdf.code_block("git reset --hard HEAD~1")
    pdf.h2("6.5 Reset sandbox branch to match development")
    pdf.body("Useful for development-local-ai when experiments went wrong:")
    pdf.code_block(
        """git fetch origin
git checkout development-local-ai
git reset --hard origin/development"""
    )
    pdf.body("This does not affect main or development on GitHub - only your local sandbox branch until you push.")
    pdf.h2("6.6 Revert a commit safely (new commit that undoes)")
    pdf.code_block(
        """git log --oneline -5
git revert <commit-hash>
git push origin development"""
    )

    # --- Troubleshooting ---
    pdf.add_page()
    pdf.h1("Part 7 - Troubleshooting")
    pdf.h2("Merge conflicts after pull")
    pdf.body("1. Git marks conflicted files. Open them and fix <<<<<<< markers.")
    pdf.body("2. git add <fixed-files>")
    pdf.body("3. git commit (merge commit) or git merge --continue")
    pdf.h2("Branch behind / ahead")
    pdf.code_block("git fetch origin\ngit status   # shows ahead/behind vs origin")
    pdf.h2("Wrong branch")
    pdf.code_block("git checkout development")
    pdf.h2("See what changed")
    pdf.code_block(
        """git diff
git diff --staged
git log -5 --oneline
git log main..development --oneline"""
    )

    # --- Pre-push checklist ---
    pdf.h1("Part 8 - Pre-Push Checklist (This Project)")
    pdf.body("Before pushing to development:")
    pdf.bullet("Update docs/source_doc.md and/or docs/tools_doc.md for code changes.")
    pdf.bullet("Log work in docs/tracker.md with accurate STATUS.")
    pdf.bullet("Run: make test && python3 -m unittest discover -s tests -q")
    pdf.bullet("Optional sync: python3 docs/cursor_helper_scripts/sync_cursor_backup.py")
    pdf.bullet("Never commit secrets (.env, tokens).")
    pdf.bullet("Push to development, not main.")

    pdf.h1("Quick Reference Card")
    pdf.code_block(
        """PULL:     git fetch && git checkout development && git pull origin development --no-rebase
COMMIT:   git add <files> && git commit -m "message"
PUSH:     git push origin development
BRANCH:   git checkout -b new-branch
MERGE:    GitHub PR development into main
RESET:    git reset --hard origin/development  (sandbox only)
BUILD:    make && make test"""
    )


def main() -> None:
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    pdf = GuidePDF()
    pdf.set_margins(18, 18, 18)
    build(pdf)
    pdf.output(str(OUT_PDF))
    print(f"Wrote {OUT_PDF}")


if __name__ == "__main__":
    main()

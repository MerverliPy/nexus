"""Git-backed note versioning — auto-commit on save, history, restore."""

import subprocess
from pathlib import Path

NOTES_REPO_DIR = Path.home() / ".nexus" / "notes"


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a git command and return the completed process."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd or NOTES_REPO_DIR),
        capture_output=True,
        text=True,
        timeout=15,
    )


def init_repo() -> bool:
    """Initialize the git repository for note versioning. Returns True on success."""
    NOTES_REPO_DIR.mkdir(parents=True, exist_ok=True)

    git_dir = NOTES_REPO_DIR / ".git"
    if git_dir.exists():
        return True

    result = subprocess.run(
        ["git", "init"],
        cwd=str(NOTES_REPO_DIR),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        return False

    # Configure git user for commits (fallback if not globally set)
    _git("config", "user.email", "nexus@localhost", cwd=NOTES_REPO_DIR)
    _git("config", "user.name", "Nexus", cwd=NOTES_REPO_DIR)

    return True


def _note_file(note_id: int) -> Path:
    """Get the file path for a note in the repo."""
    return NOTES_REPO_DIR / f"{note_id}.md"


def save_note_version(note_id: int, title: str, content: str) -> bool:
    """Save a note to the git repo and commit it. Returns True on success."""
    if not init_repo():
        return False

    file_path = _note_file(note_id)
    frontmatter = f"---\ntitle: {title}\nnote_id: {note_id}\n---\n\n"
    file_path.write_text(frontmatter + content, encoding="utf-8")

    # Stage and commit
    _git("add", str(file_path.name))
    commit_msg = f"Update: {title} (note #{note_id})"
    result = _git("commit", "-m", commit_msg, "--allow-empty")
    return result.returncode == 0


def get_note_history(note_id: int, max_count: int = 20) -> list[dict]:
    """Return git log entries for a note file."""
    if not init_repo():
        return []

    file_path = _note_file(note_id)
    if not file_path.exists():
        return []

    result = _git(
        "log",
        f"--max-count={max_count}",
        "--format=%H|%ai|%s",
        "--",
        str(file_path.name),
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    entries = []
    for line in result.stdout.strip().split("\n"):
        if "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            entries.append(
                {
                    "commit": parts[0][:8],
                    "full_commit": parts[0],
                    "date": parts[1],
                    "message": parts[2],
                }
            )
    return entries


def restore_note(note_id: int, commit_hash: str) -> str | None:
    """Restore a note's content from a specific commit. Returns content or None."""
    if not init_repo():
        return None

    file_path = _note_file(note_id)
    if not file_path.exists():
        return None

    result = _git("show", f"{commit_hash}:{file_path.name}")
    if result.returncode != 0:
        return None

    content = result.stdout

    # Strip YAML frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].strip()

    return content

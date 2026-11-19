"""Persist small pilot research archives in a dedicated Git branch, never in Actions cache."""

import argparse
import subprocess
from pathlib import Path

WORKTREE = Path("state-store")


def git(*args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], check=check, capture_output=capture, text=True)


def restore() -> None:
    if WORKTREE.exists():
        raise RuntimeError("state-store already exists; refusing to replace local data")
    remote = git("ls-remote", "--exit-code", "--heads", "origin", "lab-state", capture=True, check=False)
    if remote.returncode == 0:
        git("fetch", "--depth=1", "origin", "lab-state")
        git("worktree", "add", "--detach", str(WORKTREE), "FETCH_HEAD")
    elif remote.returncode == 2:
        git("worktree", "add", "--detach", str(WORKTREE), "HEAD")
        git("-C", str(WORKTREE), "switch", "--orphan", "lab-state")
    else:
        raise RuntimeError("Cannot read state branch; stopping instead of starting an empty journal")
    (WORKTREE / "state").mkdir(exist_ok=True)


def save() -> None:
    root = WORKTREE / "state"
    if not root.is_dir():
        raise RuntimeError("No state directory")
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_size > 80 * 1024 * 1024:
            raise RuntimeError(
                "Pilot state file exceeds 80 MiB; migrate the archive to a persistent data store"
            )
    git("-C", str(WORKTREE), "config", "user.name", "github-actions[bot]")
    git("-C", str(WORKTREE), "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    # dashboard is an export, not an authoritative journal. Avoid committing its changing timestamp.
    git("-C", str(WORKTREE), "add", "state/raw", "state/clean", "state/metadata.sqlite")
    changed = git("-C", str(WORKTREE), "diff", "--cached", "--quiet", check=False)
    if changed.returncode == 0:
        print("Research state unchanged")
        return
    if changed.returncode != 1:
        raise RuntimeError("Cannot compare state")
    git("-C", str(WORKTREE), "commit", "-m", "Persist research snapshots and append-only journals")
    git("-C", str(WORKTREE), "push", "origin", "HEAD:refs/heads/lab-state")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["restore", "save"])
    args = parser.parse_args()
    restore() if args.command == "restore" else save()

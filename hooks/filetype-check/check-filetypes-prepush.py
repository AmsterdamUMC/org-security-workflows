#!/usr/bin/env python
"""
Pre-push hook: checks files being pushed against FORBIDDEN patterns only.
Extracts patterns between "# BEGIN FORBIDDEN" and "# END FORBIDDEN"
from central-gitignore.txt

When run via pre-commit, uses PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF
environment variables to determine which files to check.
"""

import io
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from filetypes import load_forbidden_patterns, find_blocked_files, report_blocked_files

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.version_info[0] < 3:
    sys.exit("This script requires Python 3")


def run_git_command(args: list[str]) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_files_to_check() -> list[str]:
    """
    Get list of files to check based on pre-commit environment variables
    or stdin for standalone hook usage.
    """
    from_ref = os.environ.get("PRE_COMMIT_FROM_REF", "")
    to_ref = os.environ.get("PRE_COMMIT_TO_REF", "")

    if from_ref and to_ref:
        if from_ref == "0" * 40:
            output = run_git_command(["ls-tree", "-r", "--name-only", to_ref])
        else:
            output = run_git_command(
                ["diff", "--name-only", "--diff-filter=AM", f"{from_ref}..{to_ref}"]
            )
        return [f for f in output.split("\n") if f]
    else:
        files = []
        for line in sys.stdin:
            parts = line.strip().split()
            if len(parts) >= 4:
                local_sha = parts[1]
                remote_sha = parts[3]

                if remote_sha == "0" * 40:
                    output = run_git_command(["ls-tree", "-r", "--name-only", local_sha])
                else:
                    output = run_git_command(
                        ["diff", "--name-only", "--diff-filter=AM", f"{remote_sha}..{local_sha}"]
                    )
                files.extend([f for f in output.split("\n") if f])
        return files


def main() -> int:
    # Script is in hooks/filetype-check/, rules file is at repo root
    script_dir = Path(__file__).parent
    rules_file = script_dir.parent.parent / "central-gitignore.txt"

    if not rules_file.exists():
        print(f"[ERROR] central-gitignore.txt not found at: {rules_file}")
        return 1

    blocked_patterns, exception_patterns = load_forbidden_patterns(rules_file)

    if not blocked_patterns:
        print("[WARNING] No FORBIDDEN patterns found in central-gitignore.txt")
        return 0

    files = get_files_to_check()
    if not files:
        return 0

    blocked_files = find_blocked_files(files, blocked_patterns, exception_patterns)

    if blocked_files:
        report_blocked_files(blocked_files, "git push --no-verify")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
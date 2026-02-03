#!/usr/bin/env python
"""
Pre-push hook: checks files being pushed against FORBIDDEN patterns only.
Extracts patterns between "# BEGIN FORBIDDEN" and "# END FORBIDDEN"
from central-gitignore.txt

When run via pre-commit, uses PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF
environment variables to determine which files to check.
"""

import fnmatch
import io
import os
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.version_info[0] < 3:
    sys.exit("This script requires Python 3")


def load_forbidden_patterns(rules_file: Path) -> tuple[list[str], list[str]]:
    """
    Extract FORBIDDEN patterns from central-gitignore.txt.
    Returns (blocked_patterns, exception_patterns).
    """
    blocked_patterns = []
    exception_patterns = []
    in_forbidden = False

    with open(rules_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line == "# BEGIN FORBIDDEN":
                in_forbidden = True
                continue
            elif line == "# END FORBIDDEN":
                in_forbidden = False
                continue

            if not in_forbidden:
                continue

            if not line or line.startswith("#"):
                continue

            if line.startswith("!"):
                exception_patterns.append(line[1:])
            else:
                blocked_patterns.append(line)

    return blocked_patterns, exception_patterns


def matches_pattern(filepath: str, pattern: str) -> bool:
    """Check if a filename matches a glob pattern."""
    basename = Path(filepath).name

    # Handle patterns like *.csv, *.nii.gz, .env, .env.*
    if fnmatch.fnmatch(basename, pattern):
        return True

    # Handle exact matches
    if basename == pattern:
        return True

    return False


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
        # Running via pre-commit
        if from_ref == "0" * 40:
            # New branch - check all files
            output = run_git_command(["ls-tree", "-r", "--name-only", to_ref])
        else:
            # Only check added/modified files, not deleted
            output = run_git_command(
                ["diff", "--name-only", "--diff-filter=AM", f"{from_ref}..{to_ref}"]
            )
        return [f for f in output.split("\n") if f]
    else:
        # Running as standalone hook - read from stdin
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
    # Find the rules file relative to this script
    # Script is in pre-commit-check/, rules file is in repo root
    script_dir = Path(__file__).parent
    rules_file = script_dir.parent / "central-gitignore.txt"

    if not rules_file.exists():
        print(f"[ERROR] central-gitignore.txt not found at: {rules_file}")
        return 1

    # Load patterns
    blocked_patterns, exception_patterns = load_forbidden_patterns(rules_file)

    if not blocked_patterns:
        print("[WARNING] No FORBIDDEN patterns found in central-gitignore.txt")
        return 0

    # Get files to check
    files = get_files_to_check()

    if not files:
        return 0

    # Check each file
    blocked_files = []

    for filepath in files:
        is_blocked = False
        is_exception = False

        for pattern in blocked_patterns:
            if matches_pattern(filepath, pattern):
                is_blocked = True
                break

        if is_blocked and exception_patterns:
            for pattern in exception_patterns:
                if matches_pattern(filepath, pattern):
                    is_exception = True
                    break

        if is_blocked and not is_exception:
            blocked_files.append(filepath)

    if blocked_files:
        print()
        print("=" * 63)
        print("  ERROR: Forbidden file types detected!")
        print("=" * 63)
        print()
        print("The following files match forbidden data patterns:")
        print()
        for f in blocked_files:
            print(f"  ✗ {f}")
        print()
        print("These file types are blocked to prevent accidental data leaks.")
        print()
        print("If this is a false positive, contact your data steward.")
        print("To bypass (NOT recommended): git push --no-verify")
        print()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
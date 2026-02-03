#!/usr/bin/env python
"""
Pre-commit hook: checks staged files against FORBIDDEN patterns.
Extracts patterns between "# BEGIN FORBIDDEN" and "# END FORBIDDEN"
from central-gitignore.txt
"""

import sys
import fnmatch
from pathlib import Path
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
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

            # Check for section markers
            if line == "# BEGIN FORBIDDEN":
                in_forbidden = True
                continue
            elif line == "# END FORBIDDEN":
                in_forbidden = False
                continue

            # Skip if not in forbidden section
            if not in_forbidden:
                continue

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Check if it's an exception pattern (starts with !)
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

    # Get files passed as arguments (from pre-commit)
    files = sys.argv[1:]

    if not files:
        return 0

    # Check each file
    blocked_files = []

    for filepath in files:
        is_blocked = False
        is_exception = False

        # Check if file matches any blocked pattern
        for pattern in blocked_patterns:
            if matches_pattern(filepath, pattern):
                is_blocked = True
                break

        # If blocked, check if it's an exception
        if is_blocked and exception_patterns:
            for pattern in exception_patterns:
                if matches_pattern(filepath, pattern):
                    is_exception = True
                    break

        # Add to blocked list if blocked and not an exception
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
        print("To bypass (NOT recommended): git commit --no-verify")
        print()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
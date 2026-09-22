#!/usr/bin/env python
"""
Pre-commit hook: checks staged files against FORBIDDEN patterns.
Extracts patterns between "# BEGIN FORBIDDEN" and "# END FORBIDDEN"
from central-gitignore.txt

This file only selects which files to check and formats hook-specific
messages. The actual matching logic lives in filetypes.py.
"""

import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from filetypes import (
    extract_forbidden_block, find_blocked_files, report_blocked_files,
    report_corrupted_rules_file, MIN_EXPECTED_PATTERNS,
)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.version_info[0] < 3:
    sys.exit("This script requires Python 3")


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def main() -> int:
    # Script is in hooks/filetype-check/, rules file is at repo root
    script_dir = Path(__file__).parent
    rules_file = script_dir.parent.parent / "central-gitignore.txt"

    if not rules_file.exists():
        print(f"[ERROR] central-gitignore.txt not found at: {rules_file}")
        return 1

    forbidden_block, found_begin, found_end, pattern_count = extract_forbidden_block(rules_file)

    if not found_begin or not found_end or pattern_count < MIN_EXPECTED_PATTERNS:
        report_corrupted_rules_file(rules_file, found_begin, found_end, pattern_count)
        return 1

    files = sys.argv[1:] if len(sys.argv) > 1 else get_staged_files()
    if not files:
        return 0

    blocked_files = find_blocked_files(files, forbidden_block)

    if blocked_files:
        report_blocked_files(blocked_files, "git commit --no-verify")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
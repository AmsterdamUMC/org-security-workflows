#!/usr/bin/env python
"""
Pre-commit hook: checks staged files against FORBIDDEN patterns.
Extracts patterns between "# BEGIN FORBIDDEN" and "# END FORBIDDEN"
from central-gitignore.txt
"""

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from filetypes import load_forbidden_patterns, find_blocked_files, report_blocked_files

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.version_info[0] < 3:
    sys.exit("This script requires Python 3")


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

    files = sys.argv[1:]
    if not files:
        return 0

    blocked_files = find_blocked_files(files, blocked_patterns, exception_patterns)

    if blocked_files:
        report_blocked_files(blocked_files, "git commit --no-verify")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
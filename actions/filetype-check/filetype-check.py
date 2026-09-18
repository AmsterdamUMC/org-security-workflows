#!/usr/bin/env python3
"""
GitHub Action entry point for the org-security-workflows filetype
check. Checks every file tracked in the repository (not just changed
files, unlike the pre-commit/pre-push hooks) against the FORBIDDEN
block in central-gitignore.txt.

Uses the same filetypes.py the hooks use, this script only adapts the
result to GitHub Actions' output format (annotations, GITHUB_OUTPUT,
blocked_files.txt for the telemetry step).
"""

import os
import subprocess
import sys
from pathlib import Path

# This script lives at actions/filetype-check/filetype-check.py in
# org-security-workflows. The shared matching logic lives at
# hooks/filetype-check/filetypes.py in the same repo/ref, since this
# action runs from a full checkout of org-security-workflows.
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks" / "filetype-check"))

from filetypes import extract_forbidden_block, find_blocked_files

RULES_FILE = REPO_ROOT / "central-gitignore.txt"


def set_output(status: str, message: str, blocked: int, blocked_files: list[str]) -> None:
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"status={status}\n")
        f.write(f"message={message}\n")
        f.write(f"blocked={blocked}\n")
    Path("blocked_files.txt").write_text(
        "\n".join(blocked_files) + "\n" if blocked_files else ""
    )


def main() -> int:
    forbidden_block, found_begin, found_end, pattern_count = extract_forbidden_block(RULES_FILE)

    if not found_begin or not found_end:
        print("::error::central-gitignore.txt is missing BEGIN/END FORBIDDEN markers")
        set_output("fail", "corrupted_rules_file", 1, [])
        return 0

    if pattern_count == 0:
        print("No FORBIDDEN patterns found, skipping check")
        set_output("ok", "no_forbidden_patterns", 0, [])
        return 0

    result = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    all_files = [f for f in result.stdout.splitlines() if f]

    blocked_files = find_blocked_files(all_files, forbidden_block)

    if blocked_files:
        for f in blocked_files:
            print(f"::error file={f}::Blocked by FORBIDDEN patterns in central-gitignore.txt")
        print()
        print("=" * 42)
        print("ERROR: Forbidden file types detected!")
        print("=" * 42)
        print("Blocked files:")
        for f in blocked_files:
            print(f"  - {f}")
        print()
        print("These files must be removed from the repository.")
        print("See: https://github.com/AmsterdamUMC/org-security-workflows#remediation")
        set_output("fail", "forbidden_files_found", 1, blocked_files)
    else:
        print("No forbidden file types found.")
        set_output("ok", "no_forbidden_files", 0, [])

    return 0


if __name__ == "__main__":
    sys.exit(main())
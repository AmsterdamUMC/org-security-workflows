#!/usr/bin/env python3
"""
GitHub Action entry point for the org-security-workflows
personal-information check. Checks every file tracked in the
repository (not just changed files, unlike the pre-commit/pre-push
hooks) for names, addresses, and email addresses.

Uses the same personal_info.py the hooks use, this script only
adapts the result to GitHub Actions' output format (annotations,
GITHUB_OUTPUT, violation details JSON for the telemetry step).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# This script lives at actions/personal-info-check/personal-info-check.py
# in org-security-workflows. The shared matching logic and reference
# lists live at hooks/personal-info-check/ and personal-info-lists/
# in the same repo/ref, since this action runs from a full checkout
# of org-security-workflows. No need to fetch anything over HTTP.
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "hooks" / "personal-info-check"))

from personal_info import build_patterns, check_file_for_personal_info, load_reference_file

REFERENCE_DIR = REPO_ROOT / "personal-info-lists"
MAX_VIOLATION_DETAILS = 50


def set_output(status: str, violations_found: int, violation_types: list, violation_details: list) -> None:
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"status={status}\n")
        f.write(f"violations_found={violations_found}\n")
        f.write(f"violation_types={','.join(violation_types)}\n")
        f.write(f"violation_details={json.dumps(violation_details)}\n")


def main() -> int:
    firstnames_file = REFERENCE_DIR / "common-dutch-firstnames.txt"
    surnames_file = REFERENCE_DIR / "common-dutch-surnames.txt"
    streetnames_file = REFERENCE_DIR / "common-dutch-streetnames.txt"

    for name, filepath in [
        ("First names", firstnames_file),
        ("Surnames", surnames_file),
        ("Street names", streetnames_file),
    ]:
        if not filepath.exists():
            print(f"::error::{name} reference file not found: {filepath}")
            set_output("fail", 0, [], [])
            return 0

    firstnames = load_reference_file(firstnames_file)
    surnames = load_reference_file(surnames_file)
    streetnames = load_reference_file(streetnames_file)
    patterns = build_patterns(firstnames, surnames, streetnames)

    print("Scanning repository for personal information...")

    result = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    all_files = [f for f in result.stdout.splitlines() if f]

    violation_types = set()
    violation_details = []

    for filepath_str in all_files:
        filepath = Path(filepath_str)
        if not filepath.exists():
            continue
        violations = check_file_for_personal_info(filepath, patterns)
        for violation_type, line_num, _content in violations:
            violation_types.add(violation_type)
            violation_details.append(
                {"file": filepath_str, "line": line_num, "category": violation_type}
            )
            print(f"::error file={filepath_str},line={line_num}::{violation_type} detected")

    seen = set()
    deduped = []
    for v in violation_details:
        key = (v["file"], v["line"], v["category"])
        if key not in seen:
            seen.add(key)
            deduped.append(v)
    violation_details = deduped[:MAX_VIOLATION_DETAILS]

    if violation_details:
        print()
        print("Personal information detected - will fail after telemetry")
        print(f"Violations: {len(violation_details)} locations")
        set_output("fail", 1, sorted(violation_types), violation_details)
    else:
        print()
        print("No personal information detected")
        set_output("ok", 0, [], [])

    return 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python
"""
Pre-commit hook for detecting personal information.
Scans staged files for Dutch first names, surnames, street names, and email addresses.
"""

import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from personal-info import build_patterns, check_file_for_personal_info, load_reference_file

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
    # Script is in hooks/personal-info-check/, reference files are at repo root
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    reference_dir = repo_root / "personal-info-lists"

    firstnames_file = reference_dir / "common-dutch-firstnames.txt"
    surnames_file = reference_dir / "common-dutch-surnames.txt"
    streetnames_file = reference_dir / "common-dutch-streetnames.txt"

    for name, filepath in [
        ("First names", firstnames_file),
        ("Surnames", surnames_file),
        ("Street names", streetnames_file),
    ]:
        if not filepath.exists():
            print(f"ERROR: {name} reference file not found: {filepath}")
            return 1

    firstnames = load_reference_file(firstnames_file)
    surnames = load_reference_file(surnames_file)
    streetnames = load_reference_file(streetnames_file)

    patterns = build_patterns(firstnames, surnames, streetnames)

    print("Scanning staged files for personal information...")

    files = sys.argv[1:] if len(sys.argv) > 1 else get_staged_files()

    if not files:
        print("[OK] No files to check")
        return 0

    all_violations: dict[str, list[tuple[str, int, str]]] = {}

    for filepath_str in files:
        filepath = Path(filepath_str)
        if filepath.exists():
            violations = check_file_for_personal_info(filepath, patterns)
            if violations:
                all_violations[filepath_str] = violations

    if all_violations:
        print()
        for filepath, violations in all_violations.items():
            for violation_type, line_num, content in violations[:5]:
                print(f"  [{violation_type}] {filepath}:")
                truncated = content[:80] + "..." if len(content) > 80 else content
                print(f"    Line {line_num}: {truncated}")
        print()
        print("=" * 63)
        print("  ERROR: Personal information detected - commit blocked")
        print("=" * 63)
        print()
        print("Personal information was detected in your staged files.")
        print("This may include names, addresses, or email addresses.")
        print()
        print("Please remove the sensitive data before committing.")
        print()
        print("To bypass this check (NOT RECOMMENDED):")
        print("  git commit --no-verify")
        print()
        return 1
    else:
        print()
        print("[OK] No personal information detected in staged files")
        return 0


if __name__ == "__main__":
    sys.exit(main())
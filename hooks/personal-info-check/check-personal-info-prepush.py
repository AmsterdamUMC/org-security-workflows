#!/usr/bin/env python
"""
Pre-push hook for detecting personal information.
Scans files in commits about to be pushed for Dutch first names, surnames,
street names, and email addresses.
"""

import io
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from personal_info import build_patterns, check_file_for_personal_info, load_reference_file

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
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
    or by comparing with remote branch.
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
        # Running as standalone git hook - read from stdin
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
            print(f"Expected location: {reference_dir}/{filepath.name}")
            return 1

    firstnames = load_reference_file(firstnames_file)
    surnames = load_reference_file(surnames_file)
    streetnames = load_reference_file(streetnames_file)
    patterns = build_patterns(firstnames, surnames, streetnames)

    print("Scanning commits for personal information before push...")

    files = get_files_to_check()

    if not files:
        print("[OK] No files to check")
        return 0

    print(f"Checking {len(files)} changed files...")

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
        print("  ERROR: Personal information detected - push blocked")
        print("=" * 63)
        print()
        print("Personal information was detected in your commits.")
        print("This may include names, addresses, or email addresses.")
        print()
        print("Please remove the sensitive data before pushing.")
        print()
        print("To bypass this check (NOT RECOMMENDED):")
        print("  git push --no-verify")
        print()
        return 1
    else:
        print()
        print("[OK] No personal information detected in commits")
        return 0


if __name__ == "__main__":
    sys.exit(main())
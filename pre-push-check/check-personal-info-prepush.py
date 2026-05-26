#!/usr/bin/env python
"""
Pre-push hook for detecting personal information.
Scans files in commits about to be pushed for Dutch first names, surnames,
street names, patient IDs, and BSN.
"""

import io
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
if sys.version_info[0] < 3:
    sys.exit("This script requires Python 3")

# Dutch street suffixes
STREET_SUFFIXES = (
    r"straat|laan|weg|plein|gracht|kade|singel|dijk|steeg|pad|dreef|boulevard"
)


def load_reference_file(filepath: Path) -> list[str]:
    """Load a reference file and return list of entries."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def is_text_file(filepath: Path) -> bool:
    """Check if a file is a text file (not binary)."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return False
        return True
    except (IOError, OSError):
        return False


def run_git_command(args: list[str]) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_remote_branch() -> str | None:
    """Determine the remote tracking branch to compare against."""
    # Try to get upstream tracking branch
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0 and result.stdout.strip():
        remote_branch = result.stdout.strip()
        # Verify it exists
        verify = subprocess.run(
            ["git", "rev-parse", remote_branch],
            capture_output=True,
            text=True,
        )
        if verify.returncode == 0:
            return remote_branch

    # Fall back to origin/main or origin/master
    for fallback in ["origin/main", "origin/master"]:
        verify = subprocess.run(
            ["git", "rev-parse", fallback],
            capture_output=True,
            text=True,
        )
        if verify.returncode == 0:
            return fallback

    return None


def get_files_to_check() -> list[str]:
    """
    Get list of files to check based on pre-commit environment variables
    or by comparing with remote branch.
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
                [
                    "diff",
                    "--name-only",
                    "--diff-filter=AM",
                    f"{from_ref}..{to_ref}",
                ]
            )
        return [f for f in output.split("\n") if f]
    else:
        # Running as standalone hook - compare with remote branch
        remote_branch = get_remote_branch()
        if not remote_branch:
            print(
                "[WARNING] No remote branch found to compare against, skipping pre-push check"
            )
            return []

        output = run_git_command(
            [
                "diff",
                "--name-only",
                "--diff-filter=AM",
                f"{remote_branch}..HEAD",
            ]
        )
        return [f for f in output.split("\n") if f]


def is_valid_bsn(digits: str) -> bool:
    """
    Check if 9 digits pass the BSN 11-proof (elfproef).
    This reduces false positives for random 9-digit numbers.
    """
    if len(digits) != 9 or not digits.isdigit():
        return False
    # BSN 11-proof: sum of (digit * weight) must be divisible by 11
    # Weights are 9, 8, 7, 6, 5, 4, 3, 2, -1 (last digit is subtracted)
    weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
    total = sum(int(d) * w for d, w in zip(digits, weights))
    return total % 11 == 0


def build_patterns(firstnames, surnames, streetnames) -> dict:
    firstnames_pattern = (
        r"\b(" + "|".join(re.escape(n) for n in firstnames) + r")\b"
    )
    surnames_pattern = (
        r"\b(" + "|".join(re.escape(n) for n in surnames) + r")\b"
    )
    streetnames_pattern = (
        r"(" + "|".join(re.escape(s) for s in streetnames) + r")"
    )

    return {
        "patient_id": re.compile(r"\b([0-9]{7})\b"),
        "bsn": re.compile(r"\b([0-9]{9})\b"),
        "firstname_fullname": re.compile(
            firstnames_pattern + r"\s+[A-Z][a-z]{2,}"
        ),
        "surname_fullname": re.compile(r"[A-Z][a-z]{2,}\s+" + surnames_pattern),
        "street_with_number": re.compile(
            streetnames_pattern + r"\s+[0-9]", re.IGNORECASE
        ),
        "street_suffix": re.compile(
            r"\b[A-Z][a-z]{4,}(" + STREET_SUFFIXES + r")\s+[0-9]"
        ),
        "street_suffix_filter": re.compile(STREET_SUFFIXES, re.IGNORECASE),
    }


def check_file_for_personal_info(
    filepath: Path,
    patterns: dict,
) -> list[tuple[str, int, str]]:
    violations = []

    if filepath.suffix == ".md":
        return violations

    if not is_text_file(filepath):
        return violations

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except (IOError, OSError):
        return violations

    for line_num, line in enumerate(lines, 1):
        line_stripped = line.rstrip()

        if patterns["patient_id"].search(line_stripped):
            violations.append(("Patient ID", line_num, line_stripped))
            continue

        bsn_match = patterns["bsn"].search(line_stripped)
        if bsn_match and is_valid_bsn(bsn_match.group(1)):
            violations.append(("BSN", line_num, line_stripped))
            continue

        match = patterns["firstname_fullname"].search(line_stripped)
        if match and not patterns["street_suffix_filter"].search(line_stripped):
            violations.append(("Full Name", line_num, line_stripped))
            continue

        match = patterns["surname_fullname"].search(line_stripped)
        if match and not patterns["street_suffix_filter"].search(line_stripped):
            violations.append(("Full Name", line_num, line_stripped))
            continue

        if patterns["street_with_number"].search(line_stripped):
            violations.append(("Address", line_num, line_stripped))
            continue

        if patterns["street_suffix"].search(line_stripped):
            violations.append(("Address", line_num, line_stripped))
            continue

    return violations


def main() -> int:
    # Find reference files relative to this script
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    reference_dir = repo_root / "personal-info-lists"

    firstnames_file = reference_dir / "common-dutch-firstnames.txt"
    surnames_file = reference_dir / "common-dutch-surnames.txt"
    streetnames_file = reference_dir / "common-dutch-streetnames.txt"

    # Check if reference files exist
    for name, filepath in [
        ("First names", firstnames_file),
        ("Surnames", surnames_file),
        ("Street names", streetnames_file),
    ]:
        if not filepath.exists():
            print(f"ERROR: {name} reference file not found: {filepath}")
            print(f"Expected location: {reference_dir}/{filepath.name}")
            return 1

    # Load reference data
    firstnames = load_reference_file(firstnames_file)
    surnames = load_reference_file(surnames_file)
    streetnames = load_reference_file(streetnames_file)
    patterns = build_patterns(firstnames, surnames, streetnames)

    print("Scanning commits for personal information before push...")

    # Get files to check
    files = get_files_to_check()

    if not files:
        print("[OK] No files to check")
        return 0

    print(f"Checking {len(files)} changed files...")

    # Check each file
    all_violations: dict[str, list[tuple[str, int, str]]] = {}

    for filepath_str in files:
        filepath = Path(filepath_str)
        if filepath.exists():
            violations = check_file_for_personal_info(filepath, patterns)
            if violations:
                all_violations[filepath_str] = violations

    # Report results
    if all_violations:
        print()
        for filepath, violations in all_violations.items():
            for violation_type, line_num, content in violations[:5]:
                print(f"  [{violation_type}] {filepath}:")
                truncated = (
                    content[:80] + "..." if len(content) > 80 else content
                )
                print(f"    Line {line_num}: {truncated}")
        print()
        print("=" * 63)
        print("  ERROR: Personal information detected - push blocked")
        print("=" * 63)
        print()
        print("Personal information was detected in your commits.")
        print("This may include patient IDs, BSN numbers, names, or addresses.")
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

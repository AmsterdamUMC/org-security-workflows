#!/usr/bin/env python
"""
Pre-commit hook for detecting personal information.
Scans staged files for Dutch first names, surnames, street names, and patient IDs.
"""

import re
import subprocess
import sys
from pathlib import Path
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Dutch street suffixes
STREET_SUFFIXES = r"straat|laan|weg|plein|gracht|kade|singel|dijk|steeg|pad|dreef|boulevard"


def load_reference_file(filepath: Path) -> list[str]:
    """Load a reference file and return list of entries."""
    with open(filepath, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def is_text_file(filepath: Path) -> bool:
    """Check if a file is a text file (not binary)."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            # Check for null bytes (binary indicator)
            if b"\x00" in chunk:
                return False
        return True
    except (IOError, OSError):
        return False


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def check_file_for_personal_info(
    filepath: Path,
    firstnames: list[str],
    surnames: list[str],
    streetnames: list[str],
) -> list[tuple[str, int, str]]:
    """
    Check a file for personal information.
    Returns list of (violation_type, line_number, content) tuples.
    """
    violations = []

    # Skip markdown files (documentation often contains example names/addresses)
    if filepath.suffix == ".md":
        return violations

    # Skip binary files
    if not is_text_file(filepath):
        return violations

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except (IOError, OSError):
        return violations

    # Build regex patterns
    firstnames_pattern = r"\b(" + "|".join(re.escape(n) for n in firstnames) + r")\b"
    surnames_pattern = r"\b(" + "|".join(re.escape(n) for n in surnames) + r")\b"
    streetnames_pattern = r"(" + "|".join(re.escape(s) for s in streetnames) + r")"

    # Pattern for 7-digit patient IDs
    patient_id_pattern = re.compile(r"\b[0-9]{7}\b")

    # Pattern for first name followed by capitalized word
    firstname_fullname_pattern = re.compile(
        firstnames_pattern + r"\s+[A-Z][a-z]{2,}"
    )

    # Pattern for capitalized word followed by surname
    surname_fullname_pattern = re.compile(
        r"[A-Z][a-z]{2,}\s+" + surnames_pattern
    )

    # Pattern for street names with house numbers (from list)
    street_with_number_pattern = re.compile(
        streetnames_pattern + r"\s+[0-9]", re.IGNORECASE
    )
    
    # Pattern for any word ending in street suffix + number
    street_suffix_pattern = re.compile(
        r"\b[A-Z][a-z]{4,}(" + STREET_SUFFIXES + r")\s+[0-9]"
    )

    # Street suffix pattern for filtering false positives
    street_suffix_filter = re.compile(STREET_SUFFIXES, re.IGNORECASE)

    for line_num, line in enumerate(lines, 1):
        line_stripped = line.rstrip()

        # Check for 7-digit patient IDs
        if patient_id_pattern.search(line_stripped):
            violations.append(("Patient ID", line_num, line_stripped))
            continue  # One violation per line is enough

        # Check for first name followed by capitalized word (potential full name)
        match = firstname_fullname_pattern.search(line_stripped)
        if match and not street_suffix_filter.search(line_stripped):
            violations.append(("Potential Full Name", line_num, line_stripped))
            continue

        # Check for capitalized word followed by surname (potential full name)
        match = surname_fullname_pattern.search(line_stripped)
        if match and not street_suffix_filter.search(line_stripped):
            violations.append(("Potential Full Name", line_num, line_stripped))
            continue

        # Check for known street names with house numbers
        if re.search(
            streetnames_pattern + r"\s+[0-9]", line_stripped, re.IGNORECASE
        ):
            violations.append(("Address", line_num, line_stripped))
            continue

        # Check for street suffix pattern with house number
        if street_suffix_pattern.search(line_stripped):
            violations.append(("Address", line_num, line_stripped))
            continue

    return violations


def main() -> int:
    # Find reference files relative to this script
    # Script is in pre-commit-check/, reference files are in repo root
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
            return 1

    # Load reference data
    firstnames = load_reference_file(firstnames_file)
    surnames = load_reference_file(surnames_file)
    streetnames = load_reference_file(streetnames_file)

    print("🔍 Scanning staged files for personal information...")

    # Get files to check - either from arguments (pre-commit) or staged files
    files = sys.argv[1:] if len(sys.argv) > 1 else get_staged_files()

    if not files:
        print("✓ No files to check")
        return 0

    # Check each file
    all_violations: dict[str, list[tuple[str, int, str]]] = {}

    for filepath_str in files:
        filepath = Path(filepath_str)
        if filepath.exists():
            violations = check_file_for_personal_info(
                filepath, firstnames, surnames, streetnames
            )
            if violations:
                all_violations[filepath_str] = violations

    # Report results
    if all_violations:
        print()
        for filepath, violations in all_violations.items():
            for violation_type, line_num, content in violations[:5]:  # Limit to 5 per file
                print(f"  [{violation_type}] {filepath}:")
                print(f"    Line {line_num}: {content[:80]}...")
        print()
        print("=" * 63)
        print("  ⚠️  PERSONAL INFORMATION DETECTED - COMMIT BLOCKED")
        print("=" * 63)
        print()
        print("Personal information was detected in your staged files.")
        print("This may include patient IDs, names, or addresses.")
        print()
        print("Please remove the sensitive data before committing.")
        print()
        print("To bypass this check (NOT RECOMMENDED):")
        print("  git commit --no-verify")
        print()
        return 1
    else:
        print()
        print("✓ No personal information detected in staged files")
        return 0


if __name__ == "__main__":
    sys.exit(main())
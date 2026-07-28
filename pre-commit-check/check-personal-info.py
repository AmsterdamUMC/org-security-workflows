#!/usr/bin/env python
"""
Pre-commit hook for detecting personal information.
Scans staged files for Dutch first names, surnames, street names, patient IDs, and BSN.
"""

import io
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.version_info[0] < 3:
    sys.exit("This script requires Python 3")

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
    """
    Build lookup structures for personal-info detection.

    Names use set membership (O(1) lookup) instead of giant regex
    alternations, since the reference lists are large (10k-150k entries)
    and a single alternation-based regex over that many strings would be
    far too slow to run on every commit.
    """
    firstnames_set = {n.lower() for n in firstnames}
    surnames_set = {n.lower() for n in surnames}

    # Street names can be multi-word (e.g. "Van Gogh straat"), so group
    # them by word count for n-gram sliding-window matching.
    street_ngrams: dict[int, set[str]] = {}
    for s in streetnames:
        words = s.split()
        street_ngrams.setdefault(len(words), set()).add(s.lower())

    return {
        "patient_id": re.compile(r"\b([0-9]{7})\b"),
        "bsn": re.compile(r"\b([0-9]{9})\b"),
        "firstnames": firstnames_set,
        "surnames": surnames_set,
        "street_ngrams": street_ngrams,
        "street_suffix_filter": re.compile(STREET_SUFFIXES, re.IGNORECASE),
        "word_token": re.compile(r"[A-Za-z][a-zA-Z'-]*"),
    }


def check_file_for_personal_info(
    filepath: Path,
    patterns: dict,
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

    for line_num, line in enumerate(lines, 1):
        line_stripped = line.rstrip()

        if patterns["patient_id"].search(line_stripped):
            violations.append(("Patient ID", line_num, line_stripped))
            continue

        bsn_match = patterns["bsn"].search(line_stripped)
        if bsn_match and is_valid_bsn(bsn_match.group(1)):
            violations.append(("BSN", line_num, line_stripped))
            continue

        tokens = [(m.group(0), m.start()) for m in patterns["word_token"].finditer(line_stripped)]

        # --- Full name check: adjacent firstname + surname pair (case-insensitive) ---
        found_name = False
        for i in range(len(tokens) - 1):
            w1, pos1 = tokens[i]
            w2, pos2 = tokens[i + 1]
            gap = line_stripped[pos1 + len(w1):pos2]
            if gap.strip():  # must be adjacent, only whitespace between the two words
                continue
            w1_l, w2_l = w1.lower(), w2.lower()
            # Require BOTH sides to hit a lexicon (firstname->surname, or surname->firstname)
            is_pair = (
                (w1_l in patterns["firstnames"] and w2_l in patterns["surnames"])
                or (w1_l in patterns["surnames"] and w2_l in patterns["firstnames"])
            )
            if is_pair and not patterns["street_suffix_filter"].search(line_stripped):
                violations.append(("Full Name", line_num, line_stripped))
                found_name = True
                break
        if found_name:
            continue

        # --- Street name check: n-gram sliding window, longest match first ---
        words_lower = [t[0].lower() for t in tokens]
        found_street = False
        for n in sorted(patterns["street_ngrams"], reverse=True):
            candidates = patterns["street_ngrams"][n]
            for i in range(len(words_lower) - n + 1):
                phrase = " ".join(words_lower[i:i + n])
                if phrase in candidates:
                    end_pos = tokens[i + n - 1][1] + len(tokens[i + n - 1][0])
                    tail = line_stripped[end_pos:end_pos + 6]
                    if re.match(r"\s+\d", tail):
                        violations.append(("Address", line_num, line_stripped))
                    else:
                        violations.append(("Address (no number)", line_num, line_stripped))
                    found_street = True
                    break
            if found_street:
                break
        if found_street:
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

    patterns = build_patterns(firstnames, surnames, streetnames)

    print("Scanning staged files for personal information...")

    # Get files to check - either from arguments (pre-commit) or staged files
    files = sys.argv[1:] if len(sys.argv) > 1 else get_staged_files()

    if not files:
        print("[OK] No files to check")
        return 0

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
            for violation_type, line_num, content in violations[:5]:  # Limit to 5 per file
                print(f"  [{violation_type}] {filepath}:")
                truncated = content[:80] + "..." if len(content) > 80 else content
                print(f"    Line {line_num}: {truncated}")
        print()
        print("=" * 63)
        print("  ERROR: Personal information detected - commit blocked")
        print("=" * 63)
        print()
        print("Personal information was detected in your staged files.")
        print("This may include patient IDs, BSN numbers, names, or addresses.")
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
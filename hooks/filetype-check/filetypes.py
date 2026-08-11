"""
Shared forbidden-filetype detection logic for the pre-commit and
pre-push hooks. Both hooks import from here so the pattern-matching
logic only needs to be changed in one place.
"""

import fnmatch
from pathlib import Path

MIN_EXPECTED_PATTERNS = 20

def load_forbidden_patterns(rules_file: Path) -> tuple[list[str], list[str], bool, bool]:
    """
    Extract FORBIDDEN patterns from central-gitignore.txt.
    Returns (blocked_patterns, exception_patterns).
    """
    blocked_patterns = []
    exception_patterns = []
    in_forbidden = False
    found_begin = False
    found_end = False

    with open(rules_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line == "# BEGIN FORBIDDEN":
                found_begin = True
                in_forbidden = True
                continue
            elif line == "# END FORBIDDEN":
                found_end = True
                in_forbidden = False
                continue

            if not in_forbidden:
                continue
            if not line or line.startswith("#"):
                continue

            if line.startswith("!"):
                exception_patterns.append(line[1:])
            else:
                blocked_patterns.append(line)

    return blocked_patterns, exception_patterns, found_begin, found_end

def matches_pattern(filepath: str, pattern: str) -> bool:
    """Check if a filename matches a glob pattern."""
    basename = Path(filepath).name
    return fnmatch.fnmatch(basename, pattern)


def find_blocked_files(files: list[str], blocked_patterns: list[str], exception_patterns: list[str]) -> list[str]:
    """Return the subset of files that match a blocked pattern and no exception pattern."""
    blocked_files = []

    for filepath in files:
        is_blocked = any(matches_pattern(filepath, p) for p in blocked_patterns)
        is_exception = is_blocked and any(matches_pattern(filepath, p) for p in exception_patterns)

        if is_blocked and not is_exception:
            blocked_files.append(filepath)

    return blocked_files


def report_blocked_files(blocked_files: list[str], bypass_command: str) -> None:
    """Print the standard violation report."""
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
    print(f"To bypass (NOT recommended): {bypass_command}")
    print()
    

def report_corrupted_rules_file(rules_file, found_begin, found_end, pattern_count):
    print()
    print("=" * 63)
    print("  ERROR: central-gitignore.txt appears to be corrupted")
    print("=" * 63)
    if not found_begin:
        print("  - Missing '# BEGIN FORBIDDEN' marker")
    if not found_end:
        print("  - Missing '# END FORBIDDEN' marker")
    if found_begin and found_end and pattern_count < MIN_EXPECTED_PATTERNS:
        print(f"  - Only {pattern_count} pattern(s) found, expected at least {MIN_EXPECTED_PATTERNS}")
    print()
    print("Blocking commit/push as a precaution. Contact the security team.")
    print()
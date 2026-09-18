"""
Shared forbidden-filetype detection logic for the pre-commit and
pre-push hooks. Both hooks import from here so the pattern-matching
logic only needs to be changed in one place.

Matching is delegated to `git check-ignore`, Git's own .gitignore
engine, rather than a hand-rolled reimplementation, so full
.gitignore syntax (including ** and negation) works correctly.

History, for context: an earlier version used fnmatch on bare
filenames/paths, which silently dropped real .gitignore semantics
(**, directory-only patterns, negation ordering). Before that, an
even earlier version used git check-ignore directly but spawned one
subprocess per file, which benchmarked roughly 125x slower once file
counts ran into the hundreds, that slowness is why fnmatch was
introduced in the first place. Batching the whole file list into a
single `git check-ignore --stdin` call gets the correctness of Git's
real engine back without the per-file subprocess cost.

All files are checked in a single `git check-ignore --stdin` call,
not one process per file, so this stays fast even on a full-tree
check (pre-push on a new branch, or the org-wide scanner).

--no-index is required: without it, git check-ignore silently skips
paths that are already tracked/staged, which is exactly the case a
pre-commit hook needs to check.
"""

import subprocess
import tempfile
from pathlib import Path

MIN_EXPECTED_PATTERNS = 20


def extract_forbidden_block(rules_file: Path) -> tuple[str, bool, bool, int]:
    """
    Extract the lines between # BEGIN FORBIDDEN and # END FORBIDDEN
    from central-gitignore.txt, verbatim and in order (order matters
    for gitignore negation semantics).

    Returns (block_text, found_begin, found_end, pattern_count), where
    pattern_count is the number of non-comment, non-blank lines found
    (blocked and exception patterns together), used to detect a
    corrupted or truncated rules file.
    """
    lines = []
    found_begin = False
    found_end = False
    in_forbidden = False

    with open(rules_file, "r", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()

            if stripped == "# BEGIN FORBIDDEN":
                found_begin = True
                in_forbidden = True
                continue
            elif stripped == "# END FORBIDDEN":
                found_end = True
                in_forbidden = False
                continue

            if not in_forbidden:
                continue

            lines.append(raw_line.rstrip("\n"))

    pattern_count = sum(
        1 for line in lines if line.strip() and not line.strip().startswith("#")
    )

    return "\n".join(lines), found_begin, found_end, pattern_count


def find_blocked_files(files: list[str], forbidden_block: str) -> list[str]:
    """
    Return the subset of `files` that match the FORBIDDEN block,
    checked in a single git check-ignore call. See the module
    docstring for why batching and --no-index are both required.
    """
    if not files or not forbidden_block.strip():
        return []

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".gitignore", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(forbidden_block + "\n")
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "git",
                "-c", f"core.excludesfile={tmp_path}",
                "check-ignore",
                "--stdin",
                "--no-index",
            ],
            input="\n".join(files),
            capture_output=True,
            text=True,
        )
        # check-ignore exits 1 when nothing matched; that is not an
        # error for us, only an unexpected exit code is.
        if result.returncode not in (0, 1):
            raise RuntimeError(f"git check-ignore failed: {result.stderr.strip()}")
        return [line for line in result.stdout.splitlines() if line]
    finally:
        Path(tmp_path).unlink(missing_ok=True)


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
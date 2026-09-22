"""
Shared personal-information detection logic for the pre-commit and
pre-push hooks. Both hooks import from here so detection rules only
need to be changed in one place.

Unlike filetype-check, there is no single shared engine underneath
(no git check-ignore equivalent): this Python module and
personal-info.sh are two independent reimplementations of the same
rules, one per language. If you add/change a pattern or false-positive
rule here, mirror the change in personal-info.sh too, or the two
hooks will silently disagree.

Detection works on a per-line basis: build_patterns() compiles the
name/street/email regexes once from the reference lists, and
check_file_for_personal_info() scans each line of a file against
them. Markdown files are skipped entirely because documentation
routinely contains example names/addresses that would otherwise be
constant false positives.
"""


import re
from pathlib import Path

# Dutch street suffixes
STREET_SUFFIXES = r"straat|laan|weg|plein|gracht|kade|singel|dijk|steeg|pad|dreef|boulevard"

INSTITUTION_PATTERN = r"ziekenhuis|kinderziekenhuis|kliniek|hospital|clinic"
DOC_METADATA_KEYWORDS = ["author", "copyright", "maintainer", "contributor",
                          "created by", "written by", "owner", "unit owner", "code owner"]
EMAIL_PATTERN = re.compile(
    r"\b(?!(?:example|info|noreply|no-reply|support|contact|admin|webmaster|postmaster|voorbeeld|email)@)"
    r"[A-Za-z0-9._%+-]+@(?!(?:example\.com|example\.org|example\.net|example\.edu|example\.nl))"
    r"[A-Za-z0-9.-]+\.(edu|org|gov|com|net|nl|be|de|uk|fr|it|es|ch|se|no|dk|at|au|ca|jp|int|eu|ac)\b"
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


def build_patterns(firstnames, surnames, streetnames) -> dict:
    """
    Build lookup structures for personal-info detection.

    Names use set membership (O(1) lookup) instead of giant regex
    alternations, since the reference lists are large (10k-150k entries)
    and a single alternation-based regex over that many strings would be
    far too slow to run on every commit/push.

    Firstnames are single tokens (hyphenated forms like "Jan-Willem" are
    handled by word_token's character class, so no n-gram grouping is
    needed there). Surnames and street names can be multi-word (e.g.
    "ter Hart", "van der Berg", "Van Gogh straat"), so both are grouped
    by word count for n-gram sliding-window matching.

    Surnames are grouped by word count into `surname_ngrams` (a dict
    keyed by n) because multi-word surnames must be matched as a
    fixed-length phrase, not token-by-token, checking every n-gram
    length surnames actually appear in average avoids both missing
    multi-word names and matching partial fragments of them.

    Firstname/surname matching is case-sensitive; street matching is not.
    """
    firstnames_set = set(firstnames)

    surname_ngrams: dict[int, set[str]] = {}
    for s in surnames:
        words = s.split()
        surname_ngrams.setdefault(len(words), set()).add(s)

    street_ngrams: dict[int, set[str]] = {}
    for s in streetnames:
        words = s.split()
        street_ngrams.setdefault(len(words), set()).add(s.lower())

    return {
        "firstnames": firstnames_set,
        "surname_ngrams": surname_ngrams,
        "street_ngrams": street_ngrams,
        "street_suffix_filter": re.compile(STREET_SUFFIXES, re.IGNORECASE),
        "word_token": re.compile(r"[A-Za-z][a-zA-Z'-]*"),
        "email": EMAIL_PATTERN,
        "institution_filter": re.compile(INSTITUTION_PATTERN, re.IGNORECASE),
    }


def _phrase_at(tokens, line, start, n, lower=True):
    """
    Join n consecutive tokens starting at `start` into a single
    space-separated phrase.

    Surnames can be multi-word (e.g. "van der Berg"), so matching
    is done over sliding n-gram windows of tokens rather than single
    tokens; this builds the phrase for one such window so it can be
    checked against the surname list.
    """

    if start < 0 or start + n > len(tokens):
        return None
    for i in range(start, start + n - 1):
        w1, pos1 = tokens[i]
        w2, pos2 = tokens[i + 1]
        gap = line[pos1 + len(w1):pos2]
        if gap.strip():
            return None
    words = [t[0] for t in tokens[start:start + n]]
    return " ".join(w.lower() for w in words) if lower else " ".join(words)


def is_name_false_positive(line_stripped: str, patterns: dict) -> bool:
    """
    Return True if a line that matched a name pattern should be
    excluded as a false positive.

    Dutch surnames overlap heavily with ordinary words and with
    street-name components, so a raw name match alone is too noisy.
    A line is treated as a false positive if it also looks like a
    street name (suffix match), an institution name, a "post-"
    prefixed word, or a documentation/metadata line (author,
    copyright, maintainer, etc.). Those contexts are expected to
    contain real names legitimately.
    """
    if patterns["street_suffix_filter"].search(line_stripped):
        return True
    if patterns["institution_filter"].search(line_stripped):
        return True
    if "post-" in line_stripped.lower():
        return True
    if any(kw in line_stripped.lower() for kw in DOC_METADATA_KEYWORDS):
        return True
    return False


def check_file_for_personal_info(
    filepath: Path,
    patterns: dict,
) -> list[tuple[str, int, str]]:
    """
    Check a file for personal information.
    Returns list of (violation_type, line_number, content) tuples.

    Markdown files are always skipped: documentation legitimately
    contains example names, addresses, and emails, and would
    otherwise dominate the results with false positives. Binary
    files are skipped because pattern matching on non-text content
    produces meaningless matches.
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

    surname_lens = sorted(patterns["surname_ngrams"], reverse=True)
    street_lens = sorted(patterns["street_ngrams"], reverse=True)

    for line_num, line in enumerate(lines, 1):
        line_stripped = line.rstrip()

        tokens = [(m.group(0), m.start()) for m in patterns["word_token"].finditer(line_stripped)]

        if patterns["email"].search(line_stripped):
            violations.append(("Email", line_num, line_stripped))
            continue

        # --- Full name check: firstname adjacent to a (possibly multi-word) surname ---
        found_name = False
        for i, (w, pos) in enumerate(tokens):
            if w not in patterns["firstnames"]:
                continue

            # firstname followed by surname, e.g. "Simon ter Hart"
            for n in surname_lens:
                phrase = _phrase_at(tokens, line_stripped, i + 1, n, lower=False)
                if phrase and phrase in patterns["surname_ngrams"][n]:
                    if not is_name_false_positive(line_stripped, patterns):
                        violations.append(("Full Name", line_num, line_stripped))
                        found_name = True
                    break
            if found_name:
                break

            # surname followed by firstname, e.g. "ter Hart Simon"
            for n in surname_lens:
                start = i - n
                phrase = _phrase_at(tokens, line_stripped, start, n, lower=False)
                if phrase and phrase in patterns["surname_ngrams"][n]:
                    if not is_name_false_positive(line_stripped, patterns):
                        violations.append(("Full Name", line_num, line_stripped))
                        found_name = True
                    break
            if found_name:
                break
        if found_name:
            continue

        # --- Street name check: n-gram sliding window, longest match first ---
        words_lower = [t[0].lower() for t in tokens]
        found_street = False
        for n in street_lens:
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
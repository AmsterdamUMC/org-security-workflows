#!/usr/bin/env bash
# Shared forbidden-filetype detection logic for the pre-commit and
# pre-push bash hooks. Sourced, not executed directly.
#
# Delegates matching to `git check-ignore` (Git's own .gitignore
# engine) rather than hand-rolled glob matching, so full .gitignore
# syntax (including ** and negation) works correctly.
#
# History, for context: an earlier version used fnmatch-style
# matching on bare filenames/paths, which silently dropped real
# .gitignore semantics (**, directory-only patterns, negation
# ordering). Before that, an even earlier version used git
# check-ignore directly but spawned one subprocess per file, roughly
# 125x slower once file counts ran into the hundreds, that slowness
# is why fnmatch was introduced in the first place. Batching the
# whole file list into one `git check-ignore --stdin` call restores
# correctness without the per-file subprocess cost.
#
# All files are checked in a single call via --stdin, not one process
# per file, to stay fast on a full-tree check.
#
# --no-index is required: without it, git check-ignore silently skips
# paths that are already tracked/staged, which is exactly the case a
# pre-commit hook needs to check.

MIN_EXPECTED_PATTERNS=20

# Extracts the FORBIDDEN block from $1 (central-gitignore.txt) into a
# temp file (sets FORBIDDEN_TMPFILE), and sets FOUND_BEGIN, FOUND_END,
# and PATTERN_COUNT for corruption detection. Caller is responsible
# for cleaning up the temp file (trap 'rm -f "$FORBIDDEN_TMPFILE"' EXIT).
ft_extract_forbidden_block() {
    local rules_file="$1"
    FORBIDDEN_TMPFILE="$(mktemp)"
    FOUND_BEGIN=false
    FOUND_END=false
    PATTERN_COUNT=0

    local in_forbidden=false
    while IFS= read -r line; do
        line="${line%$'\r'}"

        if [[ "$line" == "# BEGIN FORBIDDEN" ]]; then
            FOUND_BEGIN=true
            in_forbidden=true
            continue
        elif [[ "$line" == "# END FORBIDDEN" ]]; then
            FOUND_END=true
            in_forbidden=false
            continue
        fi

        [[ "$in_forbidden" == false ]] && continue

        echo "$line" >> "$FORBIDDEN_TMPFILE"

        local trimmed="${line#"${line%%[![:space:]]*}"}"
        trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
        if [[ -n "$trimmed" && "$trimmed" != \#* ]]; then
            PATTERN_COUNT=$((PATTERN_COUNT + 1))
        fi
    done < "$rules_file"
}

# Populates global BLOCKED_FILES from the given files, checked in one
# batched git check-ignore call against $FORBIDDEN_TMPFILE. See the
# file header above for why batching and --no-index are both required.
ft_find_blocked_files() {
    BLOCKED_FILES=()
    local files=("$@")
    [[ ${#files[@]} -eq 0 ]] && return 0

    local output
    output=$(printf '%s\n' "${files[@]}" \
        | git -c core.excludesfile="$FORBIDDEN_TMPFILE" check-ignore --stdin --no-index)
    local status=$?

    # exit 1 = nothing matched, not an error for us
    if [[ $status -gt 1 ]]; then
        echo "[ERROR] git check-ignore failed" >&2
        return 1
    fi

    if [[ -n "$output" ]]; then
        while IFS= read -r f; do
            BLOCKED_FILES+=("$f")
        done <<< "$output"
    fi
}

ft_report_blocked_files() {
    local bypass_command="$1"
    echo ""
    echo -e "\033[1;31m══════════════════════════════════════════════════════════════\033[0m"
    echo -e "\033[1;31m  ERROR: Forbidden file types detected!\033[0m"
    echo -e "\033[1;31m══════════════════════════════════════════════════════════════\033[0m"
    echo ""
    echo "The following files match forbidden data patterns:"
    echo ""
    for f in "${BLOCKED_FILES[@]}"; do
        echo -e "  \033[33m✗\033[0m $f"
    done
    echo ""
    echo "These file types are blocked to prevent accidental data leaks."
    echo ""
    echo "If this is a false positive, contact your data steward."
    echo "To bypass (NOT recommended): $bypass_command"
    echo ""
}

ft_report_corrupted_rules_file() {
    local rules_file="$1"
    echo ""
    echo "==============================================================="
    echo "  ERROR: central-gitignore.txt appears to be corrupted"
    echo "==============================================================="
    [[ "$FOUND_BEGIN" == false ]] && echo "  - Missing '# BEGIN FORBIDDEN' marker"
    [[ "$FOUND_END" == false ]] && echo "  - Missing '# END FORBIDDEN' marker"
    if [[ "$FOUND_BEGIN" == true && "$FOUND_END" == true && "$PATTERN_COUNT" -lt "$MIN_EXPECTED_PATTERNS" ]]; then
        echo "  - Only $PATTERN_COUNT pattern(s) found, expected at least $MIN_EXPECTED_PATTERNS"
    fi
    echo ""
    echo "Blocking commit/push as a precaution. Contact the security team."
    echo ""
}
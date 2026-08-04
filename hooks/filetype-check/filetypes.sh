#!/usr/bin/env bash
# Shared forbidden-filetype detection logic for the pre-commit and
# pre-push bash hooks. Sourced, not executed directly.

# Loads central-gitignore.txt into globals BLOCKED_PATTERNS / EXCEPTION_PATTERNS
ft_load_patterns() {
    local rules_file="$1"
    BLOCKED_PATTERNS=()
    EXCEPTION_PATTERNS=()

    local in_forbidden=false
    while IFS= read -r line; do
        # Strip Windows carriage return (CRLF -> LF)
        line="${line%$'\r'}"

        if [[ "$line" == "# BEGIN FORBIDDEN" ]]; then
            in_forbidden=true
            continue
        elif [[ "$line" == "# END FORBIDDEN" ]]; then
            in_forbidden=false
            continue
        fi

        [[ "$in_forbidden" == false ]] && continue
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

        # Trim whitespace
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"

        if [[ "$line" == !* ]]; then
            EXCEPTION_PATTERNS+=("${line#!}")
        else
            BLOCKED_PATTERNS+=("${line}")
        fi
    done < "$rules_file"
}

ft_matches_pattern() {
    local file="$1"
    local pattern="$2"
    local basename="${file##*/}"
    [[ "$basename" == $pattern ]]
}

# Populates global BLOCKED_FILES from the FILES array against
# BLOCKED_PATTERNS / EXCEPTION_PATTERNS.
ft_find_blocked_files() {
    BLOCKED_FILES=()
    local file pattern is_blocked is_exception

    for file in "$@"; do
        is_blocked=false
        is_exception=false

        for pattern in "${BLOCKED_PATTERNS[@]}"; do
            if ft_matches_pattern "$file" "$pattern"; then
                is_blocked=true
                break
            fi
        done

        if [[ "$is_blocked" == true ]]; then
            for pattern in "${EXCEPTION_PATTERNS[@]}"; do
                if ft_matches_pattern "$file" "$pattern"; then
                    is_exception=true
                    break
                fi
            done
        fi

        if [[ "$is_blocked" == true && "$is_exception" == false ]]; then
            BLOCKED_FILES+=("$file")
        fi
    done
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
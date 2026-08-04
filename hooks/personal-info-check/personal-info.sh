#!/usr/bin/env bash
# Shared personal-information detection logic for the pre-commit and
# pre-push bash hooks. Sourced, not executed directly.

# Build all patterns from the reference files. Sets ALL_FIRSTNAMES,
# ALL_SURNAMES, ALL_STREETS, STREET_SUFFIXES, INSTITUTION_PATTERN,
# DOC_METADATA, EMAIL_PATTERN, IGNORED_LOCAL, IGNORED_DOMAINS as globals.
pi_load_patterns() {
    local firstnames_file="$1"
    local surnames_file="$2"
    local streetnames_file="$3"

    ALL_FIRSTNAMES=$(cat "$firstnames_file" | tr '\n' '|' | sed 's/|$//')
    ALL_SURNAMES=$(cat "$surnames_file" | tr '\n' '|' | sed 's/|$//')
    ALL_STREETS=$(cat "$streetnames_file" | tr '\n' '|' | sed 's/|$//')

    STREET_SUFFIXES="straat|laan|weg|plein|gracht|kade|singel|dijk|steeg|pad|dreef|boulevard"
    INSTITUTION_PATTERN="ziekenhuis|kinderziekenhuis|kliniek|hospital|clinic"
    DOC_METADATA="author|copyright|maintainer|contributor|created by|written by|owner|unit owner|code owner"

    # Email pattern without lookaheads: match broadly, filter ignored
    # local-parts/domains as a second pass (POSIX grep has no lookahead support).
    EMAIL_PATTERN='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(edu|org|gov|com|net|nl|be|de|uk|fr|it|es|ch|se|no|dk|at|au|ca|jp|int|eu|ac)\b'
    IGNORED_LOCAL="(example|info|noreply|no-reply|support|contact|admin|webmaster|postmaster|voorbeeld|email)@"
    IGNORED_DOMAINS="@(example\.(com|org|net|edu|nl))"
}

pi_filter_name_matches() {
    grep -ivE "($STREET_SUFFIXES)" \
        | grep -ivE "($INSTITUTION_PATTERN)" \
        | grep -v "post-" \
        | grep -ivE "($DOC_METADATA)" || true
}

# Checks $1 for personal information, printing violations using the
# color vars (RED/YELLOW/NC) and label ($2, e.g. "commit"/"push") set
# by the caller. Returns 0 if clean, 1 if violations were found.
pi_check_file() {
    local file="$1"
    local found_violation=0

    if [[ "$file" == *.md ]]; then
        return 0
    fi

    if ! file "$file" | grep -q "text"; then
        return 0
    fi

    # Email addresses
    if grep -qE "$EMAIL_PATTERN" "$file"; then
        MATCHES=$(grep -nE "$EMAIL_PATTERN" "$file" | grep -viE "$IGNORED_LOCAL" | grep -viE "$IGNORED_DOMAINS" || true)
        if [[ -n "$MATCHES" ]]; then
            echo -e "  ${RED}[Email]${NC} Email address found in ${YELLOW}$file${NC}:"
            echo "$MATCHES" | head -3 | while IFS=: read -r line_num content; do
                echo -e "    Line $line_num: $content"
            done
            found_violation=1
        fi
    fi

    # Full names: firstname + surname, either order, both sides in lexicon, case-sensitive
    if grep -qE "\b($ALL_FIRSTNAMES)\s+($ALL_SURNAMES)\b" "$file"; then
        MATCHES=$(grep -E "\b($ALL_FIRSTNAMES)\s+($ALL_SURNAMES)\b" "$file" | pi_filter_name_matches)
        if [[ -n "$MATCHES" ]]; then
            echo -e "  ${RED}[Full Name]${NC} Firstname + surname in ${YELLOW}$file${NC}:"
            echo "$MATCHES" | head -3 | while IFS= read -r line; do
                LINE_NUM=$(grep -nF "$line" "$file" | head -1 | cut -d: -f1)
                echo -e "    Line $LINE_NUM: $line"
            done
            found_violation=1
        fi
    fi

    if grep -qE "\b($ALL_SURNAMES)\s+($ALL_FIRSTNAMES)\b" "$file"; then
        MATCHES=$(grep -E "\b($ALL_SURNAMES)\s+($ALL_FIRSTNAMES)\b" "$file" | pi_filter_name_matches)
        if [[ -n "$MATCHES" ]]; then
            echo -e "  ${RED}[Full Name]${NC} Surname + firstname in ${YELLOW}$file${NC}:"
            echo "$MATCHES" | head -3 | while IFS= read -r line; do
                LINE_NUM=$(grep -nF "$line" "$file" | head -1 | cut -d: -f1)
                echo -e "    Line $LINE_NUM: $line"
            done
            found_violation=1
        fi
    fi

    # Known street + house number (no generic suffix fallback)
    if grep -iqE "($ALL_STREETS)[[:space:]]+[0-9]" "$file"; then
        echo -e "  ${RED}[Address]${NC} Street name with house number in ${YELLOW}$file${NC}:"
        grep -inE "($ALL_STREETS)[[:space:]]+[0-9]" "$file" | head -3 | while IFS=: read -r line_num content; do
            echo -e "    Line $line_num: $content"
        done
        found_violation=1
    fi

    return $found_violation
}
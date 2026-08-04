#!/usr/bin/env bash
# Pre-push hook for detecting personal information
# Scans commits about to be pushed for Dutch first names, surnames, street names, and email addresses

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/personal_info.sh"

if [[ -t 1 ]]; then
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    GREEN='\033[0;32m'
    NC='\033[0m'
else
    RED=''
    YELLOW=''
    GREEN=''
    NC=''
fi

REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REFERENCE_DIR="$REPO_ROOT/personal-info-lists"

FIRSTNAMES_FILE="${PERSONAL_INFO_FIRSTNAMES_FILE:-$REFERENCE_DIR/common-dutch-firstnames.txt}"
SURNAMES_FILE="${PERSONAL_INFO_SURNAMES_FILE:-$REFERENCE_DIR/common-dutch-surnames.txt}"
STREETNAMES_FILE="${PERSONAL_INFO_STREETNAMES_FILE:-$REFERENCE_DIR/common-dutch-streetnames.txt}"

for f in "$FIRSTNAMES_FILE" "$SURNAMES_FILE" "$STREETNAMES_FILE"; do
    if [[ ! -f "$f" ]]; then
        echo -e "${RED}ERROR: reference file not found: $f${NC}"
        exit 1
    fi
done

echo -e "${YELLOW}🔍 Scanning commits for personal information before push...${NC}"

pi_load_patterns "$FIRSTNAMES_FILE" "$SURNAMES_FILE" "$STREETNAMES_FILE"

# Determine files to check: pre-commit passes FROM_REF/TO_REF; standalone
# git hook reads local/remote SHAs from stdin.
get_files_to_check() {
    if [[ -n "$PRE_COMMIT_FROM_REF" && -n "$PRE_COMMIT_TO_REF" ]]; then
        if [[ "$PRE_COMMIT_FROM_REF" == "0000000000000000000000000000000000000000" ]]; then
            git ls-tree -r --name-only "$PRE_COMMIT_TO_REF"
        else
            git diff --name-only --diff-filter=AM "$PRE_COMMIT_FROM_REF..$PRE_COMMIT_TO_REF"
        fi
    else
        while read -r _ local_sha _ remote_sha; do
            [[ -z "$local_sha" ]] && continue
            if [[ "$remote_sha" == "0000000000000000000000000000000000000000" ]]; then
                git ls-tree -r --name-only "$local_sha"
            else
                git diff --name-only --diff-filter=AM "$remote_sha..$local_sha"
            fi
        done
    fi
}

FILES=$(get_files_to_check)
if [[ -z "$FILES" ]]; then
    echo -e "${GREEN}✓ No files to check${NC}"
    exit 0
fi

VIOLATIONS_FOUND=0
while IFS= read -r file; do
    if [[ -f "$file" ]]; then
        if ! pi_check_file "$file"; then
            VIOLATIONS_FOUND=1
        fi
    fi
done <<< "$FILES"

if [[ $VIOLATIONS_FOUND -eq 1 ]]; then
    echo ""
    echo -e "${RED}╔═════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ⚠️  PERSONAL INFORMATION DETECTED - PUSH BLOCKED         ║${NC}"
    echo -e "${RED}╚═════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Personal information was detected in your commits.${NC}"
    echo -e "${YELLOW}This may include names, addresses, or email addresses.${NC}"
    echo ""
    echo -e "${YELLOW}Please remove the sensitive data before pushing.${NC}"
    echo ""
    echo "To bypass this check (NOT RECOMMENDED):"
    echo "  git push --no-verify"
    echo ""
    exit 1
else
    echo ""
    echo -e "${GREEN}✓ No personal information detected in commits${NC}"
    exit 0
fi
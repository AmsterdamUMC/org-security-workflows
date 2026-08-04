#!/usr/bin/env bash
# Pre-commit hook for detecting personal information
# Scans staged files for Dutch first names, surnames, street names, and email addresses

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

echo -e "${YELLOW}🔍 Scanning staged files for personal information...${NC}"

STAGED_COUNT=$(git diff --cached --name-only --diff-filter=ACM | wc -l)
if [[ "$STAGED_COUNT" -eq 0 ]]; then
    echo -e "${GREEN}✓ No staged files to check${NC}"
    exit 0
fi

pi_load_patterns "$FIRSTNAMES_FILE" "$SURNAMES_FILE" "$STREETNAMES_FILE"

VIOLATIONS_FOUND=0
while IFS= read -r -d '' file; do
    if [[ -f "$file" ]]; then
        if ! pi_check_file "$file"; then
            VIOLATIONS_FOUND=1
        fi
    fi
done < <(git diff --cached --name-only --diff-filter=ACM -z)

if [[ $VIOLATIONS_FOUND -eq 1 ]]; then
    echo ""
    echo -e "${RED}╔═════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ⚠️  PERSONAL INFORMATION DETECTED - COMMIT BLOCKED       ║${NC}"
    echo -e "${RED}╚═════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Personal information was detected in your staged files.${NC}"
    echo -e "${YELLOW}This may include names, addresses, or email addresses.${NC}"
    echo ""
    echo -e "${YELLOW}Please remove the sensitive data before committing.${NC}"
    echo ""
    echo "To bypass this check (NOT RECOMMENDED):"
    echo "  git commit --no-verify"
    echo ""
    exit 1
else
    echo ""
    echo -e "${GREEN}✓ No personal information detected in staged files${NC}"
    exit 0
fi
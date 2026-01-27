#!/usr/bin/env bash
# Pre-push hook for detecting personal information
# Scans files in commits about to be pushed for Dutch first names, surnames, street names, and patient IDs

set -e

# Detect if terminal supports colors
if [[ -t 1 ]]; then
    # Terminal - use colors
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    GREEN='\033[0;32m'
    NC='\033[0m' # No Color
else
    # Non-terminal (VSCode, pipes, etc.) - no colors
    RED=''
    YELLOW=''
    GREEN=''
    NC=''
fi

# Path to reference files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REFERENCE_DIR="$REPO_ROOT/personal-info-lists"

FIRSTNAMES_FILE="${PERSONAL_INFO_FIRSTNAMES_FILE:-$REFERENCE_DIR/common-dutch-firstnames.txt}"
SURNAMES_FILE="${PERSONAL_INFO_SURNAMES_FILE:-$REFERENCE_DIR/common-dutch-surnames.txt}"
STREETNAMES_FILE="${PERSONAL_INFO_STREETNAMES_FILE:-$REFERENCE_DIR/common-dutch-streetnames.txt}"

# Check if reference files exist
if [[ ! -f "$FIRSTNAMES_FILE" ]]; then
    echo -e "${RED}ERROR: First names reference file not found: $FIRSTNAMES_FILE${NC}"
    echo "Expected location: $REFERENCE_DIR/common-dutch-firstnames.txt"
    exit 1
fi

if [[ ! -f "$SURNAMES_FILE" ]]; then
    echo -e "${RED}ERROR: Surnames reference file not found: $SURNAMES_FILE${NC}"
    echo "Expected location: $REFERENCE_DIR/common-dutch-surnames.txt"
    exit 1
fi

if [[ ! -f "$STREETNAMES_FILE" ]]; then
    echo -e "${RED}ERROR: Street names reference file not found: $STREETNAMES_FILE${NC}"
    echo "Expected location: $REFERENCE_DIR/common-dutch-streetnames.txt"
    exit 1
fi

echo -e "${YELLOW}🔍 Scanning commits for personal information before push...${NC}"

# Get current branch name
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Determine the remote tracking branch
REMOTE_BRANCH=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "origin/$CURRENT_BRANCH")

# If remote branch doesn't exist, compare with main/master
if ! git rev-parse "$REMOTE_BRANCH" >/dev/null 2>&1; then
    if git rev-parse origin/main >/dev/null 2>&1; then
        REMOTE_BRANCH="origin/main"
    elif git rev-parse origin/master >/dev/null 2>&1; then
        REMOTE_BRANCH="origin/master"
    else
        echo -e "${YELLOW}⚠️  No remote branch found to compare against, skipping pre-push check${NC}"
        exit 0
    fi
fi

# Check if there are any changed files
CHANGED_COUNT=$(git diff --name-only "$REMOTE_BRANCH"..HEAD 2>/dev/null | wc -l || echo "0")

if [[ "$CHANGED_COUNT" -eq 0 ]]; then
    echo -e "${GREEN}✓ No files to check${NC}"
    exit 0
fi

echo -e "${YELLOW}Checking $CHANGED_COUNT changed files...${NC}"

# Build combined patterns for fast initial checks
ALL_FIRSTNAMES=$(cat "$FIRSTNAMES_FILE" | tr '\n' '|' | sed 's/|$//')
ALL_SURNAMES=$(cat "$SURNAMES_FILE" | tr '\n' '|' | sed 's/|$//')
ALL_STREETS=$(cat "$STREETNAMES_FILE" | tr '\n' '|' | sed 's/|$//')

# Dutch street suffixes
STREET_SUFFIXES="straat|laan|weg|plein|gracht|kade|singel|dijk|steeg|pad|dreef|boulevard"

# Initialize violation flag
VIOLATIONS_FOUND=0

# Function to check for matches in a file
check_file_for_personal_info() {
    local file=$1
    local found_violation=0
    
    # Skip markdown files (documentation often contains example names/addresses)
    if [[ "$file" == *.md ]]; then
        return 0
    fi

    # Skip if file doesn't exist (deleted files)
    if [[ ! -f "$file" ]]; then
        return 0
    fi
    
    # Skip binary files
    if ! file "$file" | grep -q "text"; then
        return 0
    fi
    
    # Check for 7-digit patient IDs
    if grep -qE '\b[0-9]{7}\b' "$file"; then
        echo -e "  ${RED}[Patient ID]${NC} 7-digit numbers found in ${YELLOW}$file${NC}:"
        grep -nE '\b[0-9]{7}\b' "$file" | head -5 | while IFS=: read -r line_num content; do
            echo -e "    Line $line_num: $content"
        done
        found_violation=1
    fi
    
    # PHASE 1: Fast check - does file contain ANY first name?
    if grep -qE "\b($ALL_FIRSTNAMES)\b" "$file"; then
        # PHASE 2: Check for first name followed by capitalized word (potential full name)
        # BUT exclude matches that are street names (contain street suffixes)
        
        # First, get lines with potential names
        POTENTIAL_NAMES=$(grep -E "\b($ALL_FIRSTNAMES)\s+[A-Z][a-z]{2,}" "$file" || true)
        
        if [[ -n "$POTENTIAL_NAMES" ]]; then
            # Filter out lines that contain street suffixes
            FILTERED_NAMES=$(echo "$POTENTIAL_NAMES" | grep -ivE "($STREET_SUFFIXES)" || true)
            
            if [[ -n "$FILTERED_NAMES" ]]; then
                echo -e "  ${RED}[Potential Full Name]${NC} First name followed by capitalized word in ${YELLOW}$file${NC}:"
                echo "$FILTERED_NAMES" | head -3 | while IFS= read -r line; do
                    # Get line number for this match
                    LINE_NUM=$(grep -nF "$line" "$file" | head -1 | cut -d: -f1)
                    echo -e "    Line $LINE_NUM: $line"
                done
                found_violation=1
            fi
        fi
    fi
    
    # PHASE 1: Fast check - does file contain ANY surname?
    if [[ $found_violation -eq 0 ]] && grep -qE "\b($ALL_SURNAMES)\b" "$file"; then
        # PHASE 2: Check for capitalized word followed by surname (potential full name)
        # BUT exclude matches that are street names (contain street suffixes)
        
        # First, get lines with potential names
        POTENTIAL_NAMES=$(grep -E "[A-Z][a-z]{2,}\s+\b($ALL_SURNAMES)\b" "$file" || true)
        
        if [[ -n "$POTENTIAL_NAMES" ]]; then
            # Filter out lines that contain street suffixes
            FILTERED_NAMES=$(echo "$POTENTIAL_NAMES" | grep -ivE "($STREET_SUFFIXES)" || true)
            
            if [[ -n "$FILTERED_NAMES" ]]; then
                echo -e "  ${RED}[Potential Full Name]${NC} Capitalized word followed by surname in ${YELLOW}$file${NC}:"
                echo "$FILTERED_NAMES" | head -3 | while IFS= read -r line; do
                    # Get line number for this match
                    LINE_NUM=$(grep -nF "$line" "$file" | head -1 | cut -d: -f1)
                    echo -e "    Line $LINE_NUM: $line"
                done
                found_violation=1
            fi
        fi
    fi
    
    # Check for street names WITH house numbers only (actual addresses)
    
    # 1. Known street names from list + number
    if grep -iqE "($ALL_STREETS)[[:space:]]+[0-9]" "$file"; then
        echo -e "  ${RED}[Address]${NC} Street name with house number in ${YELLOW}$file${NC}:"
        grep -inE "($ALL_STREETS)[[:space:]]+[0-9]" "$file" | head -3 | while IFS=: read -r line_num content; do
            echo -e "    Line $line_num: $content"
        done
        found_violation=1
    fi
    
    # 2. Any word ending in street suffix + number (Stationstraat 123, Hoofdweg 45, etc.)
    if grep -qE "\b[A-Z][a-z]{4,}($STREET_SUFFIXES)[[:space:]]+[0-9]" "$file"; then
        echo -e "  ${RED}[Address]${NC} Street pattern with house number in ${YELLOW}$file${NC}:"
        grep -nE "\b[A-Z][a-z]{4,}($STREET_SUFFIXES)[[:space:]]+[0-9]" "$file" | head -3 | while IFS=: read -r line_num content; do
            echo -e "    Line $line_num: $content"
        done
        found_violation=1
    fi
    
    if [[ $found_violation -eq 1 ]]; then
        return 1  # Return 1 = found violation (error/failure)
    else
        return 0  # Return 0 = no violation (success)
    fi
}

# Check each changed file using null-delimited output
while IFS= read -r -d '' file; do
    if [[ -f "$file" ]]; then
        if ! check_file_for_personal_info "$file"; then
            VIOLATIONS_FOUND=1
        fi
    fi
done < <(git diff --name-only -z "$REMOTE_BRANCH
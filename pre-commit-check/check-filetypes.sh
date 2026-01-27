#!/usr/bin/env bash
#
# Pre-commit hook: checks staged files against FORBIDDEN patterns only
# Extracts patterns between "# BEGIN FORBIDDEN" and "# END FORBIDDEN"
# from central-gitignore.txt
#
set -euo pipefail

RULES_FILE="$(dirname "${BASH_SOURCE[0]}")/../central-gitignore.txt"

if [[ ! -f "$RULES_FILE" ]]; then
  echo "[ERROR] central-gitignore.txt not found at: $RULES_FILE"
  exit 1
fi

# Extract only FORBIDDEN sections
# Stores blocked patterns and exception patterns separately
BLOCKED_PATTERNS=()
EXCEPTION_PATTERNS=()

in_forbidden=false
while IFS= read -r line; do
  # Check for section markers
  if [[ "$line" == "# BEGIN FORBIDDEN" ]]; then
    in_forbidden=true
    continue
  elif [[ "$line" == "# END FORBIDDEN" ]]; then
    in_forbidden=false
    continue
  fi

  # Skip if not in forbidden section
  [[ "$in_forbidden" == false ]] && continue

  # Skip comments and empty lines
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

  # Trim whitespace
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"

  # Check if it's an exception pattern (starts with !)
  if [[ "$line" == !* ]]; then
    EXCEPTION_PATTERNS+=("${line#!}")
  else
    BLOCKED_PATTERNS+=("${line}")
  fi
done < "$RULES_FILE"

if [[ ${#BLOCKED_PATTERNS[@]} -eq 0 ]]; then
  echo "[WARNING] No FORBIDDEN patterns found in central-gitignore.txt"
  exit 0
fi

# Get files passed as arguments (from pre-commit)
FILES=("$@")

if [[ ${#FILES[@]} -eq 0 ]]; then
  exit 0
fi

# Function to check if a filename matches a glob pattern
matches_pattern() {
  local file="$1"
  local pattern="$2"
  local basename="${file##*/}"

  # Handle patterns like *.csv, *.nii.gz
  if [[ "$pattern" == \** ]]; then
    [[ "$basename" == $pattern ]] && return 0
  # Handle patterns like .env, .env.*
  elif [[ "$pattern" == .* ]]; then
    [[ "$basename" == $pattern ]] && return 0
  # Handle exact matches
  elif [[ "$basename" == "$pattern" ]]; then
    return 0
  fi

  return 1
}

BLOCKED=0
BLOCKED_FILES=()

for FILE in "${FILES[@]}"; do
  is_blocked=false
  is_exception=false

  # Check if file matches any blocked pattern
  for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if matches_pattern "$FILE" "$pattern"; then
      is_blocked=true
      break
    fi
  done

  # If blocked, check if it's an exception
  if [[ "$is_blocked" == true ]]; then
    for pattern in "${EXCEPTION_PATTERNS[@]}"; do
      if matches_pattern "$FILE" "$pattern"; then
        is_exception=true
        break
      fi
    done
  fi

  # Add to blocked list if blocked and not an exception
  if [[ "$is_blocked" == true && "$is_exception" == false ]]; then
    BLOCKED_FILES+=("$FILE")
    BLOCKED=1
  fi
done

if [[ $BLOCKED -eq 1 ]]; then
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
  echo "To bypass (NOT recommended): git commit --no-verify"
  echo ""
  exit 1
fi

exit 0
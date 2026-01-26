#!/usr/bin/env bash
#
# Pre-push hook: checks files being pushed against FORBIDDEN patterns only
# Downloads central-gitignore.txt and extracts FORBIDDEN sections
#
# When run via pre-commit, uses PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF
# environment variables to determine which files to check.
#
set -euo pipefail

RULES_URL="https://raw.githubusercontent.com/AmsterdamUMC/org-security-workflows/main/central-gitignore.txt"

TMP_DIR="$(mktemp -d)"
TMP_GITIGNORE="$TMP_DIR/central-gitignore.txt"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# Download central gitignore
if ! curl -sL "$RULES_URL" -o "$TMP_GITIGNORE"; then
  echo "[ERROR] Could not download central-gitignore.txt from:"
  echo "  $RULES_URL"
  exit 1
fi

# Extract only FORBIDDEN sections
BLOCKED_PATTERNS=()
EXCEPTION_PATTERNS=()

in_forbidden=false
while IFS= read -r line; do
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
done < "$TMP_GITIGNORE"

if [[ ${#BLOCKED_PATTERNS[@]} -eq 0 ]]; then
  echo "[WARNING] No FORBIDDEN patterns found in central-gitignore.txt"
  exit 0
fi

# Function to check if a filename matches a glob pattern
matches_pattern() {
  local file="$1"
  local pattern="$2"
  local basename="${file##*/}"

  if [[ "$pattern" == \** ]]; then
    [[ "$basename" == $pattern ]] && return 0
  elif [[ "$pattern" == .* ]]; then
    [[ "$basename" == $pattern ]] && return 0
  elif [[ "$basename" == "$pattern" ]]; then
    return 0
  fi

  return 1
}

# Get files to check
# pre-commit sets PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF for pre-push
if [[ -n "${PRE_COMMIT_FROM_REF:-}" && -n "${PRE_COMMIT_TO_REF:-}" ]]; then
  # Running via pre-commit
  if [[ "$PRE_COMMIT_FROM_REF" == "0000000000000000000000000000000000000000" ]]; then
    # New branch - check all files
    FILES=$(git ls-tree -r --name-only "$PRE_COMMIT_TO_REF")
  else
    # Only check added/modified files, not deleted (--diff-filter=AM)
    FILES=$(git diff --name-only --diff-filter=AM "$PRE_COMMIT_FROM_REF..$PRE_COMMIT_TO_REF" 2>/dev/null || echo "")
  fi
else
  # Running as standalone hook - read from stdin
  while read -r local_ref local_sha remote_ref remote_sha; do
    if [[ "$remote_sha" == "0000000000000000000000000000000000000000" ]]; then
      FILES=$(git ls-tree -r --name-only "$local_sha")
    else
      # Only check added/modified files, not deleted (--diff-filter=AM)
      FILES=$(git diff --name-only --diff-filter=AM "$remote_sha..$local_sha" 2>/dev/null || echo "")
    fi
  done
fi

if [[ -z "${FILES:-}" ]]; then
  exit 0
fi

BLOCKED_FILES=()

for FILE in $FILES; do
  is_blocked=false
  is_exception=false

  for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if matches_pattern "$FILE" "$pattern"; then
      is_blocked=true
      break
    fi
  done

  if [[ "$is_blocked" == true ]]; then
    for pattern in "${EXCEPTION_PATTERNS[@]}"; do
      if matches_pattern "$FILE" "$pattern"; then
        is_exception=true
        break
      fi
    done
  fi

  if [[ "$is_blocked" == true && "$is_exception" == false ]]; then
    BLOCKED_FILES+=("$FILE")
  fi
done

if (( ${#BLOCKED_FILES[@]} > 0 )); then
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
  echo "To bypass (NOT recommended): git push --no-verify"
  echo ""
  exit 1
fi

exit 0
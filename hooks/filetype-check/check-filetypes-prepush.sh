#!/usr/bin/env bash
# Pre-push hook: checks files being pushed against FORBIDDEN patterns only
#
# When run via pre-commit, uses PRE_COMMIT_FROM_REF and PRE_COMMIT_TO_REF
# environment variables to determine which files to check.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/filetypes.sh"

RULES_FILE="$SCRIPT_DIR/../../central-gitignore.txt"

if [[ ! -f "$RULES_FILE" ]]; then
  echo "[ERROR] central-gitignore.txt not found at: $RULES_FILE"
  exit 1
fi

ft_load_patterns "$RULES_FILE"

if [[ ${#BLOCKED_PATTERNS[@]} -eq 0 ]]; then
  echo "[WARNING] No FORBIDDEN patterns found in central-gitignore.txt"
  exit 0
fi

if [[ -n "${PRE_COMMIT_FROM_REF:-}" && -n "${PRE_COMMIT_TO_REF:-}" ]]; then
  if [[ "$PRE_COMMIT_FROM_REF" == "0000000000000000000000000000000000000000" ]]; then
    FILES=$(git ls-tree -r --name-only "$PRE_COMMIT_TO_REF")
  else
    FILES=$(git diff --name-only --diff-filter=AM "$PRE_COMMIT_FROM_REF..$PRE_COMMIT_TO_REF" 2>/dev/null || echo "")
  fi
else
  while read -r local_ref local_sha remote_ref remote_sha; do
    if [[ "$remote_sha" == "0000000000000000000000000000000000000000" ]]; then
      FILES=$(git ls-tree -r --name-only "$local_sha")
    else
      FILES=$(git diff --name-only --diff-filter=AM "$remote_sha..$local_sha" 2>/dev/null || echo "")
    fi
  done
fi

if [[ -z "${FILES:-}" ]]; then
  exit 0
fi

ft_find_blocked_files $FILES

if (( ${#BLOCKED_FILES[@]} > 0 )); then
  ft_report_blocked_files "git push --no-verify"
  exit 1
fi

exit 0
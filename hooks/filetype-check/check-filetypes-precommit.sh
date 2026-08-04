#!/usr/bin/env bash
# Pre-commit hook: checks staged files against FORBIDDEN patterns only
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

FILES=("$@")
if [[ ${#FILES[@]} -eq 0 ]]; then
  exit 0
fi

ft_find_blocked_files "${FILES[@]}"

if (( ${#BLOCKED_FILES[@]} > 0 )); then
  ft_report_blocked_files "git commit --no-verify"
  exit 1
fi

exit 0
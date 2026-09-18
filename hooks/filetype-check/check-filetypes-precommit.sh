#!/usr/bin/env bash
# Pre-commit hook: checks staged files against FORBIDDEN patterns only
#
# This file only selects which files to check and formats hook-specific
# messages. The actual matching logic lives in filetypes.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/filetypes.sh"

RULES_FILE="$SCRIPT_DIR/../../central-gitignore.txt"

if [[ ! -f "$RULES_FILE" ]]; then
  echo "[ERROR] central-gitignore.txt not found at: $RULES_FILE"
  exit 1
fi

ft_extract_forbidden_block "$RULES_FILE"
trap 'rm -f "$FORBIDDEN_TMPFILE"' EXIT

if [[ "$FOUND_BEGIN" == false || "$FOUND_END" == false || "$PATTERN_COUNT" -lt "$MIN_EXPECTED_PATTERNS" ]]; then
  ft_report_corrupted_rules_file "$RULES_FILE"
  exit 1
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
# Design

## Scope: all tracked files, not a diff

Unlike the pre-commit/pre-push hooks (which check only staged files
or a commit range), this action checks every file currently tracked
in the repository (`git ls-files`) on each run. This catches
violations in files that existed before the hooks were installed, or
that were committed with `--no-verify`.

## No HTTP fetch for shared logic or rules

This action runs from a full checkout of org-security-workflows at
its own ref (github.action_path points inside that checkout), so
filetypes.py and central-gitignore.txt are already on disk. An
earlier version curl-fetched central-gitignore.txt from a
raw.githubusercontent.com URL with a configurable repo/ref; that
network dependency and its inputs were removed since the data was
always available locally already.

## Logic lives in a real script file, not inline YAML

filetype-check.py is a standalone, runnable Python file that imports
filetypes.py directly, same module the hooks use. action.yml only
invokes it (`python3 filetype-check.py`). Detection logic used to be
inline bash inside action.yml's run: block, reimplemented separately
from the hooks; that duplication was the source of a real bug (see
hooks/filetype-check/DESIGN.md's matching-engine history) before it
was consolidated here.

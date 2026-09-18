# Filetype Detection: Design

## Purpose

Blocks committing/pushing files whose name matches a forbidden
pattern (data files, medical imaging formats, credentials, etc.),
defined once in central-gitignore.txt's FORBIDDEN block. Used by the
pre-commit hook, pre-push hook, and the GitHub Action, all via the
same shared module (filetypes.py / filetypes.sh). Works purely on
filenames; file contents are never read.

## Rules source

central-gitignore.txt at the repo root. Lines between
`# BEGIN FORBIDDEN` and `# END FORBIDDEN` are extracted verbatim, in
order (order matters for gitignore negation semantics). Lines
starting with `!` are exceptions. This same file is also the source
for repo-template-secure's static .gitignore copy.

## Matching engine: git check-ignore, not a hand-rolled matcher

Matching is delegated to `git check-ignore`, Git's own .gitignore
engine, rather than reimplementing glob matching. This gives full
.gitignore syntax for free: directory-scoped patterns (/data/*, which
matches at any depth since a single `*` here crosses directory
boundaries, intentionally broader than real .gitignore, which would
need /data/** for that), and negations scoped to a specific path
(!data/.gitkeep only excepts that file inside data/, not files with
the same name elsewhere).

History: an earlier version used git check-ignore directly but spawned
one subprocess per file, which benchmarked ~125x slower once file
counts ran into the hundreds (a real concern for pre-push on a new
branch, or an org-wide scan). That was replaced with fnmatch-based
matching on bare filenames/paths, which silently dropped real
.gitignore semantics (no directory scoping, no working negation with
paths). The current version restores git check-ignore but batches the
entire file list into a single `--stdin` call, getting Git's
correctness back without the per-file cost.

`--no-index` is required on that call: without it, git check-ignore
silently skips paths that are already tracked or staged, which is
exactly the case a pre-commit hook needs to check (confirmed by
direct testing: a staged forbidden file was silently exempted without
this flag).

## Corruption detection

If the BEGIN/END markers are missing, or the number of extracted
patterns is suspiciously low (below MIN_EXPECTED_PATTERNS), the
commit/push is blocked as a precaution rather than silently checking
against an empty or malformed ruleset. This guards against a broken
edit to central-gitignore.txt silently disabling protection for every
repository at once.

## Shared module, not duplicated per entry point

filetypes.py / filetypes.sh contain all of the above. The precommit
and prepush entry scripts (both languages), and the GitHub Action's
filetype-check.py, only differ in how they select which files to
check and in their user-facing messages.
"""
Golden-fixture tests for find_blocked_files(): each directory under
tests/fixtures/filetypes/ holds a rules.txt (a FORBIDDEN block),
files.json (candidate filenames), and expected.json (which of those
should be blocked).

real-forbidden-patterns/ uses the actual central-gitignore.txt block,
so it reflects real policy; the others exercise gitignore engine
semantics (negation ordering, **) that are otherwise easy to
regress, since they're the reason this module shells out to git
check-ignore instead of reimplementing glob matching (see
filetypes.py's module docstring).

Adding coverage means adding a fixture directory, not editing this
file.
"""

import json

import pytest

import filetypes as ft
from conftest import FIXTURES_DIR

FILETYPES_FIXTURES_DIR = FIXTURES_DIR / "filetypes"
FIXTURE_CASES = sorted(p for p in FILETYPES_FIXTURES_DIR.iterdir() if p.is_dir())


@pytest.mark.parametrize("case_dir", FIXTURE_CASES, ids=lambda p: p.name)
def test_fixture(case_dir, git_repo):
    forbidden_block = (case_dir / "rules.txt").read_text()
    files = json.loads((case_dir / "files.json").read_text())
    expected = json.loads((case_dir / "expected.json").read_text())

    blocked = ft.find_blocked_files(files, forbidden_block)

    assert sorted(blocked) == sorted(expected)

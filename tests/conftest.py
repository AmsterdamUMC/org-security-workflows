"""
Test setup shared by all test modules.

The modules under test (filetypes.py, personal_info.py) live in
hooks/*/ rather than an installable package, so they're not import-
able by path alone; this adds both directories to sys.path once, the
same way the hook and action entry points do at runtime.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(REPO_ROOT / "hooks" / "filetype-check"))
sys.path.insert(0, str(REPO_ROOT / "hooks" / "personal-info-check"))

import personal_info as pi  # noqa: E402


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    """
    An empty git repo in a temp dir, chdir'd into.

    find_blocked_files() shells out to `git check-ignore`, which
    refuses to run outside a git working tree (even with --no-index),
    and runs relative to the process cwd. Using the real repo's
    working tree would let its own .gitignore/excludes leak into
    results, so tests get an isolated throwaway repo instead.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture(scope="session")
def real_patterns():
    """
    Patterns built from the actual reference lists, not a synthetic
    lexicon, so personal-info fixtures exercise the real word lists
    researchers' commits are checked against, not a stand-in for them.
    Session-scoped since building this from ~280k reference lines is
    the most expensive part of these tests (though still ~0.1s).
    """
    reference_dir = REPO_ROOT / "personal-info-lists"
    firstnames = pi.load_reference_file(reference_dir / "common-dutch-firstnames.txt")
    surnames = pi.load_reference_file(reference_dir / "common-dutch-surnames.txt")
    streetnames = pi.load_reference_file(reference_dir / "common-dutch-streetnames.txt")
    return pi.build_patterns(firstnames, surnames, streetnames)

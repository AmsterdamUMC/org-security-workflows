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
    # Local (not global) config, so committing works the same in CI
    # as on a dev machine with no git identity configured yet.
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def commit_file(repo: Path, filename: str, content: str) -> str:
    """
    Write filename with content, `git add` + `git commit` it in repo,
    and return the resulting commit SHA. Used to build up commit
    history with known SHAs for the pre-push hook tests, which take
    a from/to ref pair (env vars or stdin) rather than a working-tree
    diff.
    """
    (repo / filename).write_text(content)
    subprocess.run(["git", "add", filename], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"add {filename}"], cwd=repo, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def run_hook(script: Path, args=None, cwd=None, env=None, stdin_text=None) -> subprocess.CompletedProcess:
    """
    Run a hook entry-point script as a real subprocess, the same way
    git/pre-commit invoke it. Hook filenames contain hyphens
    (check-personal-info-precommit.py), so they can't be `import`ed
    as ordinary modules; importlib-based loading would also dodge
    the exact failure mode ("hyphenated module import breakage")
    these scripts have broken on before, so subprocess is used
    instead of working around that.
    """
    import os

    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(script)] + (args or []),
        cwd=cwd,
        env=full_env,
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def run_action(script: Path, cwd: Path) -> tuple[subprocess.CompletedProcess, dict]:
    """
    Run a GitHub Actions entry-point script (actions/*/*.py) as a real
    subprocess against cwd (a real git repo with tracked files),
    providing a GITHUB_OUTPUT file the same way the Actions runner
    does. Returns (process, parsed GITHUB_OUTPUT key/value pairs):
    these scripts always exit 0 and signal pass/fail through
    GITHUB_OUTPUT's `status` field instead of the process exit code,
    so the exit code alone isn't enough to assert against.
    """
    import os

    output_file = cwd / "github_output.txt"
    output_file.write_text("")
    full_env = dict(os.environ)
    full_env["GITHUB_OUTPUT"] = str(output_file)

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=full_env,
        capture_output=True,
        text=True,
    )

    output = {}
    for line in output_file.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            output[key] = value
    return result, output


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

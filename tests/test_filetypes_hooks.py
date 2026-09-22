"""
Integration tests for the filetype-check hook entry-point scripts,
run as real subprocesses against real throwaway git repos (see
run_hook()/git_repo/commit_file() in conftest.py for why).

These check the wiring — does the script find the right files and
translate a blocked file into the right exit code and message — not
the pattern-matching logic itself, which is already covered by
test_filetypes_fixtures.py. Uses the real central-gitignore.txt (its
path is hardcoded relative to the script location, not overridable),
so "*.csv" and "notes.txt" below are chosen against real policy.
"""

import subprocess

from conftest import REPO_ROOT, commit_file, run_hook

PRECOMMIT = REPO_ROOT / "hooks" / "filetype-check" / "check-filetypes-precommit.py"
PREPUSH = REPO_ROOT / "hooks" / "filetype-check" / "check-filetypes-prepush.py"

ALL_ZERO_SHA = "0" * 40


class TestPrecommit:
    def test_no_staged_files(self, git_repo):
        result = run_hook(PRECOMMIT, cwd=git_repo)
        assert result.returncode == 0

    def test_clean_staged_file_passes(self, git_repo):
        (git_repo / "notes.txt").write_text("hello\n")
        subprocess.run(["git", "add", "notes.txt"], cwd=git_repo, check=True)

        result = run_hook(PRECOMMIT, cwd=git_repo)

        assert result.returncode == 0

    def test_forbidden_staged_file_blocks(self, git_repo):
        (git_repo / "data.csv").write_text("a,b\n1,2\n")
        subprocess.run(["git", "add", "data.csv"], cwd=git_repo, check=True)

        result = run_hook(PRECOMMIT, cwd=git_repo)

        assert result.returncode == 1
        assert "data.csv" in result.stdout
        assert "Forbidden file types detected" in result.stdout

    def test_argv_files_override_staged_files(self, git_repo):
        # Pre-commit-framework invocation path: filenames passed as
        # argv, not relying on the git-staged fallback.
        (git_repo / "notes.txt").write_text("hello\n")
        subprocess.run(["git", "add", "notes.txt"], cwd=git_repo, check=True)
        (git_repo / "data.csv").write_text("a,b\n1,2\n")  # not staged

        result = run_hook(PRECOMMIT, args=["data.csv"], cwd=git_repo)

        assert result.returncode == 1
        assert "data.csv" in result.stdout

    def test_falls_back_to_staged_files_with_no_argv(self, git_repo):
        # Regression test for the staged-files fallback added to this
        # script (it previously only ever read argv).
        (git_repo / "data.csv").write_text("a,b\n1,2\n")
        subprocess.run(["git", "add", "data.csv"], cwd=git_repo, check=True)

        result = run_hook(PRECOMMIT, cwd=git_repo)

        assert result.returncode == 1
        assert "data.csv" in result.stdout


class TestPrepushEnvMode:
    """PRE_COMMIT_FROM_REF / PRE_COMMIT_TO_REF, as set by the pre-commit framework."""

    def test_new_branch_checks_every_file_in_ref(self, git_repo):
        sha = commit_file(git_repo, "data.csv", "a,b\n1,2\n")
        env = {"PRE_COMMIT_FROM_REF": ALL_ZERO_SHA, "PRE_COMMIT_TO_REF": sha}

        result = run_hook(PREPUSH, cwd=git_repo, env=env)

        assert result.returncode == 1
        assert "data.csv" in result.stdout

    def test_existing_branch_diffs_only_new_commits(self, git_repo):
        sha1 = commit_file(git_repo, "notes.txt", "hello\n")
        sha2 = commit_file(git_repo, "data.csv", "a,b\n1,2\n")
        env = {"PRE_COMMIT_FROM_REF": sha1, "PRE_COMMIT_TO_REF": sha2}

        result = run_hook(PREPUSH, cwd=git_repo, env=env)

        assert result.returncode == 1
        assert "data.csv" in result.stdout
        assert "notes.txt" not in result.stdout

    def test_existing_branch_clean_passes(self, git_repo):
        sha1 = commit_file(git_repo, "a.txt", "hello\n")
        sha2 = commit_file(git_repo, "b.txt", "hello again\n")
        env = {"PRE_COMMIT_FROM_REF": sha1, "PRE_COMMIT_TO_REF": sha2}

        result = run_hook(PREPUSH, cwd=git_repo, env=env)

        assert result.returncode == 0


class TestPrepushStdinMode:
    """
    Standalone git pre-push hook invocation: git writes one line per
    ref being pushed to stdin, as "<local ref> <local sha>
    <remote ref> <remote sha>".
    """

    def test_new_branch_via_stdin(self, git_repo):
        sha = commit_file(git_repo, "data.csv", "a,b\n1,2\n")
        stdin_text = f"refs/heads/main {sha} refs/heads/main {ALL_ZERO_SHA}\n"

        result = run_hook(PREPUSH, cwd=git_repo, stdin_text=stdin_text)

        assert result.returncode == 1
        assert "data.csv" in result.stdout

    def test_existing_branch_via_stdin(self, git_repo):
        sha1 = commit_file(git_repo, "notes.txt", "hello\n")
        sha2 = commit_file(git_repo, "data.csv", "a,b\n1,2\n")
        stdin_text = f"refs/heads/main {sha2} refs/heads/main {sha1}\n"

        result = run_hook(PREPUSH, cwd=git_repo, stdin_text=stdin_text)

        assert result.returncode == 1
        assert "data.csv" in result.stdout

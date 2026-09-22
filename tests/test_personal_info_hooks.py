"""
Integration tests for the personal-info hook entry-point scripts,
run as real subprocesses against real throwaway git repos (see
run_hook()/git_repo/commit_file() in conftest.py for why).

These check the wiring — does the script find the right files and
translate a violation into the right exit code and message — not the
detection logic itself, which is already covered by
test_personal_info_fixtures.py.
"""

import subprocess

from conftest import REPO_ROOT, commit_file, run_hook

PRECOMMIT = REPO_ROOT / "hooks" / "personal-info-check" / "check-personal-info-precommit.py"
PREPUSH = REPO_ROOT / "hooks" / "personal-info-check" / "check-personal-info-prepush.py"

ALL_ZERO_SHA = "0" * 40
FLAGGED_CONTENT = "Simon Hart signed off on this.\n"
CLEAN_CONTENT = "Nothing sensitive in here.\n"


class TestPrecommit:
    def test_no_staged_files(self, git_repo):
        result = run_hook(PRECOMMIT, cwd=git_repo)
        assert result.returncode == 0
        assert "No files to check" in result.stdout

    def test_clean_staged_file_passes(self, git_repo):
        (git_repo / "notes.txt").write_text(CLEAN_CONTENT)
        subprocess.run(["git", "add", "notes.txt"], cwd=git_repo, check=True)

        result = run_hook(PRECOMMIT, cwd=git_repo)

        assert result.returncode == 0
        assert "No personal information detected" in result.stdout

    def test_flagged_staged_file_blocks(self, git_repo):
        (git_repo / "notes.txt").write_text(FLAGGED_CONTENT)
        subprocess.run(["git", "add", "notes.txt"], cwd=git_repo, check=True)

        result = run_hook(PRECOMMIT, cwd=git_repo)

        assert result.returncode == 1
        assert "Full Name" in result.stdout
        assert "commit blocked" in result.stdout

    def test_argv_files_override_staged_files(self, git_repo):
        # This is the pre-commit-framework invocation path: it passes
        # filenames as argv rather than relying on the git-staged
        # fallback. A file on disk but not staged should still be
        # checked when named explicitly.
        (git_repo / "clean.txt").write_text(CLEAN_CONTENT)
        subprocess.run(["git", "add", "clean.txt"], cwd=git_repo, check=True)
        (git_repo / "dirty.txt").write_text(FLAGGED_CONTENT)

        result = run_hook(PRECOMMIT, args=["dirty.txt"], cwd=git_repo)

        assert result.returncode == 1
        assert "dirty.txt" in result.stdout


class TestPrepushEnvMode:
    """PRE_COMMIT_FROM_REF / PRE_COMMIT_TO_REF, as set by the pre-commit framework."""

    def test_new_branch_checks_every_file_in_ref(self, git_repo):
        sha = commit_file(git_repo, "notes.txt", FLAGGED_CONTENT)
        env = {"PRE_COMMIT_FROM_REF": ALL_ZERO_SHA, "PRE_COMMIT_TO_REF": sha}

        result = run_hook(PREPUSH, cwd=git_repo, env=env)

        assert result.returncode == 1
        assert "Full Name" in result.stdout

    def test_existing_branch_diffs_only_new_commits(self, git_repo):
        sha1 = commit_file(git_repo, "clean.txt", CLEAN_CONTENT)
        sha2 = commit_file(git_repo, "dirty.txt", FLAGGED_CONTENT)
        env = {"PRE_COMMIT_FROM_REF": sha1, "PRE_COMMIT_TO_REF": sha2}

        result = run_hook(PREPUSH, cwd=git_repo, env=env)

        assert result.returncode == 1
        assert "dirty.txt" in result.stdout
        assert "clean.txt" not in result.stdout

    def test_existing_branch_clean_passes(self, git_repo):
        sha1 = commit_file(git_repo, "a.txt", CLEAN_CONTENT)
        sha2 = commit_file(git_repo, "b.txt", "Still nothing sensitive.\n")
        env = {"PRE_COMMIT_FROM_REF": sha1, "PRE_COMMIT_TO_REF": sha2}

        result = run_hook(PREPUSH, cwd=git_repo, env=env)

        assert result.returncode == 0
        assert "No personal information detected" in result.stdout


class TestPrepushStdinMode:
    """
    Standalone git pre-push hook invocation: git writes one line per
    ref being pushed to stdin, as "<local ref> <local sha>
    <remote ref> <remote sha>".
    """

    def test_new_branch_via_stdin(self, git_repo):
        sha = commit_file(git_repo, "notes.txt", FLAGGED_CONTENT)
        stdin_text = f"refs/heads/main {sha} refs/heads/main {ALL_ZERO_SHA}\n"

        result = run_hook(PREPUSH, cwd=git_repo, stdin_text=stdin_text)

        assert result.returncode == 1
        assert "Full Name" in result.stdout

    def test_existing_branch_via_stdin(self, git_repo):
        sha1 = commit_file(git_repo, "clean.txt", CLEAN_CONTENT)
        sha2 = commit_file(git_repo, "dirty.txt", FLAGGED_CONTENT)
        stdin_text = f"refs/heads/main {sha2} refs/heads/main {sha1}\n"

        result = run_hook(PREPUSH, cwd=git_repo, stdin_text=stdin_text)

        assert result.returncode == 1
        assert "dirty.txt" in result.stdout

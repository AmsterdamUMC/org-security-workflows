"""
Integration tests for actions/filetype-check/filetype-check.py, the
GitHub Action entry point. Uses find_blocked_files() (already covered
by test_filetypes_fixtures.py), so what's actually being checked here
is the action-specific glue that has no hook equivalent: scoping to
`git ls-files` (repo-tracked files, not staged/diffed), and signaling
pass/fail through $GITHUB_OUTPUT rather than the process exit code
(this script always exits 0 — see run_action() in conftest.py).
"""

import subprocess

from conftest import REPO_ROOT, run_action

SCRIPT = REPO_ROOT / "actions" / "filetype-check" / "filetype-check.py"


class TestFiletypeCheckAction:
    def test_no_tracked_files(self, git_repo):
        result, output = run_action(SCRIPT, git_repo)

        assert result.returncode == 0
        assert output["status"] == "ok"
        assert output["blocked"] == "0"

    def test_clean_tracked_file_passes(self, git_repo):
        (git_repo / "notes.txt").write_text("hello\n")
        subprocess.run(["git", "add", "notes.txt"], cwd=git_repo, check=True)

        result, output = run_action(SCRIPT, git_repo)

        assert result.returncode == 0
        assert output["status"] == "ok"
        assert output["message"] == "no_forbidden_files"
        assert output["blocked"] == "0"
        assert (git_repo / "blocked_files.txt").read_text() == ""

    def test_forbidden_tracked_file_fails(self, git_repo):
        (git_repo / "data.csv").write_text("a,b\n1,2\n")
        subprocess.run(["git", "add", "data.csv"], cwd=git_repo, check=True)

        result, output = run_action(SCRIPT, git_repo)

        assert result.returncode == 0  # this script always exits 0
        assert output["status"] == "fail"
        assert output["message"] == "forbidden_files_found"
        assert output["blocked"] == "1"
        assert "data.csv" in (git_repo / "blocked_files.txt").read_text()
        assert "::error file=data.csv::" in result.stdout

    def test_untracked_forbidden_file_is_not_checked(self, git_repo):
        # git ls-files only lists what's in the index; an untracked
        # file on disk shouldn't be picked up at all, unlike the
        # hooks' staged-files fallback.
        (git_repo / "data.csv").write_text("a,b\n1,2\n")

        result, output = run_action(SCRIPT, git_repo)

        assert output["status"] == "ok"
        assert output["blocked"] == "0"

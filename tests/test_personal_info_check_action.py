"""
Integration tests for actions/personal-info-check/personal-info-check.py,
the GitHub Action entry point. Uses check_file_for_personal_info()
(already covered by test_personal_info_fixtures.py), so what's
actually being checked here is the action-specific glue that has no
hook equivalent: scoping to `git ls-files` (repo-tracked files, not
staged/diffed), the violation_details JSON written to $GITHUB_OUTPUT,
and signaling pass/fail through $GITHUB_OUTPUT rather than the
process exit code (this script always exits 0 — see run_action() in
conftest.py).
"""

import json
import subprocess

from conftest import REPO_ROOT, run_action

SCRIPT = REPO_ROOT / "actions" / "personal-info-check" / "personal-info-check.py"


class TestPersonalInfoCheckAction:
    def test_no_tracked_files(self, git_repo):
        result, output = run_action(SCRIPT, git_repo)

        assert result.returncode == 0
        assert output["status"] == "ok"
        assert output["violations_found"] == "0"

    def test_clean_tracked_file_passes(self, git_repo):
        (git_repo / "notes.txt").write_text("Nothing sensitive here.\n")
        subprocess.run(["git", "add", "notes.txt"], cwd=git_repo, check=True)

        result, output = run_action(SCRIPT, git_repo)

        assert result.returncode == 0
        assert output["status"] == "ok"
        assert output["violations_found"] == "0"
        assert output["violation_types"] == ""

    def test_flagged_tracked_file_fails(self, git_repo):
        (git_repo / "notes.txt").write_text("Simon Hart signed off on this.\n")
        subprocess.run(["git", "add", "notes.txt"], cwd=git_repo, check=True)

        result, output = run_action(SCRIPT, git_repo)

        assert result.returncode == 0  # this script always exits 0
        assert output["status"] == "fail"
        assert output["violations_found"] == "1"
        assert "Full Name" in output["violation_types"]
        assert "::error file=notes.txt,line=1::" in result.stdout

        details = json.loads(output["violation_details"])
        assert details == [{"file": "notes.txt", "line": 1, "category": "Full Name"}]

    def test_untracked_flagged_file_is_not_checked(self, git_repo):
        # git ls-files only lists what's in the index; an untracked
        # file on disk shouldn't be picked up at all, unlike the
        # hooks' staged-files fallback.
        (git_repo / "notes.txt").write_text("Simon Hart signed off on this.\n")

        result, output = run_action(SCRIPT, git_repo)

        assert output["status"] == "ok"
        assert output["violations_found"] == "0"

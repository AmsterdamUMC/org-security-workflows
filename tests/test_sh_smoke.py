"""
Smoke tests for the bash shared libraries (personal-info.sh,
filetypes.sh). These are treated as legacy: they're an independent
reimplementation of personal_info.py's rules using single regex
alternations against raw text rather than personal_info.py's
tokenized n-gram matching, so they were never guaranteed to agree on
anything beyond simple cases, and asserting behavioral parity would
mean either hard-coding "these are allowed to disagree here" per
edge case or failing on day one. See the project discussion in
DESIGN.md for the full reasoning.

What these tests check instead: that sourcing the scripts and calling
their functions against real input doesn't blow up (no bash syntax
error, no unbound-variable crash, no command-not-found from a typo'd
helper). That's the failure mode most likely to slip in silently,
since nothing exercises these scripts in CI otherwise.
"""

import subprocess

from conftest import FIXTURES_DIR, REPO_ROOT

PERSONAL_INFO_SH = REPO_ROOT / "hooks" / "personal-info-check" / "personal-info.sh"
FILETYPES_SH = REPO_ROOT / "hooks" / "filetype-check" / "filetypes.sh"
REFERENCE_DIR = REPO_ROOT / "personal-info-lists"

PERSONAL_INFO_INPUT_FILES = sorted(
    (FIXTURES_DIR / "personal-info").glob("*/input.*")
)


def _run_bash(script: str, cwd) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


class TestPersonalInfoShSmoke:
    def test_sourcing_does_not_error(self, tmp_path):
        result = _run_bash(f"source '{PERSONAL_INFO_SH}'", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_pi_load_patterns_does_not_error(self, tmp_path):
        script = f"""
        source '{PERSONAL_INFO_SH}'
        pi_load_patterns \
            '{REFERENCE_DIR / "common-dutch-firstnames.txt"}' \
            '{REFERENCE_DIR / "common-dutch-surnames.txt"}' \
            '{REFERENCE_DIR / "common-dutch-streetnames.txt"}'
        """
        result = _run_bash(script, tmp_path)
        assert result.returncode == 0, result.stderr

    def test_pi_check_file_does_not_crash_on_any_fixture(self, tmp_path):
        for input_file in PERSONAL_INFO_INPUT_FILES:
            script = f"""
            source '{PERSONAL_INFO_SH}'
            RED='' YELLOW='' NC=''
            pi_load_patterns \
                '{REFERENCE_DIR / "common-dutch-firstnames.txt"}' \
                '{REFERENCE_DIR / "common-dutch-surnames.txt"}' \
                '{REFERENCE_DIR / "common-dutch-streetnames.txt"}'
            pi_check_file '{input_file}' 'test'
            """
            result = _run_bash(script, tmp_path)
            # 0 (clean) or 1 (violations found) are the only expected
            # exit codes; anything else means the script itself broke.
            assert result.returncode in (0, 1), (
                f"{input_file.relative_to(REPO_ROOT)}: exit {result.returncode}\n{result.stderr}"
            )
            assert "syntax error" not in result.stderr
            assert "command not found" not in result.stderr


class TestFiletypesShSmoke:
    def test_sourcing_does_not_error(self, tmp_path):
        result = _run_bash(f"source '{FILETYPES_SH}'", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_extract_and_find_blocked_files_does_not_crash(self, git_repo):
        rules = git_repo / "rules.txt"
        rules.write_text("# BEGIN FORBIDDEN\n*.pdf\n# END FORBIDDEN\n")
        (git_repo / "report.pdf").touch()
        (git_repo / "notes.txt").touch()
        script = f"""
        source '{FILETYPES_SH}'
        trap 'rm -f "$FORBIDDEN_TMPFILE"' EXIT
        ft_extract_forbidden_block '{rules}'
        ft_find_blocked_files report.pdf notes.txt
        printf '%s\\n' "${{BLOCKED_FILES[@]}}"
        """
        result = _run_bash(script, git_repo)
        assert result.returncode == 0, result.stderr
        assert "report.pdf" in result.stdout

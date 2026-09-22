import filetypes as ft


class TestExtractForbiddenBlock:
    def test_extracts_lines_between_markers(self, tmp_path):
        rules = tmp_path / "rules.txt"
        rules.write_text(
            "# comment before\n"
            "# BEGIN FORBIDDEN\n"
            "*.pdf\n"
            "*.docx\n"
            "# END FORBIDDEN\n"
            "*.ignored\n"
        )
        block, found_begin, found_end, count = ft.extract_forbidden_block(rules)
        assert found_begin is True
        assert found_end is True
        assert block == "*.pdf\n*.docx"
        assert count == 2

    def test_missing_begin_marker(self, tmp_path):
        rules = tmp_path / "rules.txt"
        rules.write_text("*.pdf\n# END FORBIDDEN\n")
        _, found_begin, found_end, _ = ft.extract_forbidden_block(rules)
        assert found_begin is False
        assert found_end is True

    def test_missing_end_marker(self, tmp_path):
        rules = tmp_path / "rules.txt"
        rules.write_text("# BEGIN FORBIDDEN\n*.pdf\n")
        _, found_begin, found_end, _ = ft.extract_forbidden_block(rules)
        assert found_begin is True
        assert found_end is False

    def test_pattern_count_ignores_comments_and_blanks(self, tmp_path):
        rules = tmp_path / "rules.txt"
        rules.write_text(
            "# BEGIN FORBIDDEN\n"
            "# a comment\n"
            "\n"
            "*.pdf\n"
            "# END FORBIDDEN\n"
        )
        _, _, _, count = ft.extract_forbidden_block(rules)
        assert count == 1


class TestFindBlockedFiles:
    # Only the argument-shape edge cases live here (empty inputs);
    # actual pattern-matching behavior is covered by the golden
    # fixtures in test_filetypes_fixtures.py.
    def test_empty_files_returns_empty(self, git_repo):
        assert ft.find_blocked_files([], "*.pdf") == []

    def test_empty_forbidden_block_returns_empty(self, git_repo):
        assert ft.find_blocked_files(["a.pdf"], "   ") == []


class TestReportFunctions:
    def test_report_blocked_files_lists_files_and_bypass(self, capsys):
        ft.report_blocked_files(["secrets.pdf"], "git commit --no-verify")
        out = capsys.readouterr().out
        assert "secrets.pdf" in out
        assert "git commit --no-verify" in out

    def test_report_corrupted_rules_file_missing_begin(self, capsys):
        ft.report_corrupted_rules_file("rules.txt", found_begin=False, found_end=True, pattern_count=5)
        out = capsys.readouterr().out
        assert "Missing '# BEGIN FORBIDDEN'" in out

    def test_report_corrupted_rules_file_too_few_patterns(self, capsys):
        ft.report_corrupted_rules_file("rules.txt", found_begin=True, found_end=True, pattern_count=1)
        out = capsys.readouterr().out
        assert "Only 1 pattern(s) found" in out

"""
Unit tests for the small pure-function building blocks of
personal_info.py. End-to-end detection behavior (does this file
content get flagged, and as what) is covered by the golden-fixture
tests in test_personal_info_fixtures.py instead, since that's real
file content rather than isolated function calls.
"""

import pytest

import personal_info as pi


@pytest.fixture
def patterns():
    return pi.build_patterns(
        firstnames=["Simon", "Anna", "Jan-Willem"],
        surnames=["Hart", "ter Hart", "van der Berg"],
        streetnames=["Kalverstraat", "Van Gogh straat"],
    )


class TestLoadReferenceFile:
    def test_strips_and_skips_blank_lines(self, tmp_path):
        f = tmp_path / "names.txt"
        f.write_text("Anna\n\n  Simon  \n\n")
        assert pi.load_reference_file(f) == ["Anna", "Simon"]


class TestIsTextFile:
    def test_text_file(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hello")
        assert pi.is_text_file(f) is True

    def test_binary_file(self, tmp_path):
        f = tmp_path / "a.bin"
        f.write_bytes(b"\x00\x01\x02")
        assert pi.is_text_file(f) is False

    def test_missing_file(self, tmp_path):
        assert pi.is_text_file(tmp_path / "missing") is False


class TestPhraseAt:
    def test_adjacent_tokens_join_lowercased(self):
        line = "van der Berg"
        tokens = [("van", 0), ("der", 4), ("Berg", 8)]
        assert pi._phrase_at(tokens, line, 0, 3) == "van der berg"

    def test_adjacent_tokens_join_original_case(self):
        line = "van der Berg"
        tokens = [("van", 0), ("der", 4), ("Berg", 8)]
        assert pi._phrase_at(tokens, line, 0, 3, lower=False) == "van der Berg"

    def test_non_adjacent_tokens_return_none(self):
        # A non-whitespace character between two tokens (e.g. a comma)
        # means they aren't a real multi-word phrase.
        line = "van,der Berg"
        tokens = [("van", 0), ("der", 4), ("Berg", 8)]
        assert pi._phrase_at(tokens, line, 0, 2) is None

    def test_out_of_range_returns_none(self):
        line = "van der"
        tokens = [("van", 0), ("der", 4)]
        assert pi._phrase_at(tokens, line, 0, 3) is None
        assert pi._phrase_at(tokens, line, -1, 1) is None


class TestIsNameFalsePositive:
    def test_street_suffix_triggers_false_positive(self, patterns):
        assert pi.is_name_false_positive("Simon lives on Kalverstraat", patterns) is True

    def test_institution_triggers_false_positive(self, patterns):
        assert pi.is_name_false_positive("Simon works at the ziekenhuis", patterns) is True

    def test_post_prefix_triggers_false_positive(self, patterns):
        assert pi.is_name_false_positive("Simon post-Hart merge", patterns) is True

    def test_doc_metadata_keyword_triggers_false_positive(self, patterns):
        assert pi.is_name_false_positive("# Author: Simon Hart", patterns) is True

    def test_plain_name_is_not_a_false_positive(self, patterns):
        assert pi.is_name_false_positive("Simon Hart signed the form", patterns) is False

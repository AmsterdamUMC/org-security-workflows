"""
Golden-fixture tests for check_file_for_personal_info(): each
directory under tests/fixtures/personal-info/ holds a real input file
plus an expected.json describing what should (or shouldn't) be
flagged in it. Built against the real reference lists (see the
real_patterns fixture in conftest.py) so these reflect what a
researcher's commit would actually trigger, not a synthetic lexicon.

Adding coverage means adding a fixture directory, not editing this
file.
"""

import json

import pytest

import personal_info as pi
from conftest import FIXTURES_DIR

PERSONAL_INFO_FIXTURES_DIR = FIXTURES_DIR / "personal-info"
FIXTURE_CASES = sorted(p for p in PERSONAL_INFO_FIXTURES_DIR.iterdir() if p.is_dir())


@pytest.mark.parametrize("case_dir", FIXTURE_CASES, ids=lambda p: p.name)
def test_fixture(case_dir, real_patterns):
    input_file = next(case_dir.glob("input.*"))
    expected = json.loads((case_dir / "expected.json").read_text())

    violations = pi.check_file_for_personal_info(input_file, real_patterns)
    actual = [{"type": v[0], "line": v[1]} for v in violations]

    assert actual == expected

from __future__ import annotations

import json

import pytest

from ai import guardrails
from ai.demo_provider import FIXTURE_PATH


@pytest.mark.parametrize("text", [
    "The candidate is competent in crimping.",
    "Candidate is not yet competent.",
    "He would pass this PC.",
    "This attempt failed the criterion.",
    "The candidate is qualified as an electrician.",
    "We certify this work.",
    "Certified assessment outcome.",
    "A score of 3 is appropriate.",
    "This deserves 3/4.",
    "Rated 3 out of 4.",
    "The candidate should be awarded full marks.",
    "Give 4 marks.",
    "उम्मीदवार सक्षम है।",
    "वह पास है",
    "यह फेल हो गया",
    "उम्मीदवार योग्य है",
])
def test_detects_verdicts(text):
    assert guardrails.find_violations(text), text
    out = guardrails.neutralise(text)
    assert not out.ok
    assert guardrails.NOTICE in out.text
    # the neutralised text itself must be clean apart from the notice
    assert not guardrails.find_violations(out.text.replace(guardrails.NOTICE, ""))


@pytest.mark.parametrize("text", [
    "Candidate strips conductor insulation with an insulated wire stripper.",
    "The cable passes through the trunking.",
    "Potential evidence supporting PC10 found at 00:42–01:08.",
    "Whether the work meets the standard is for the assessor to judge against the rubric.",
    "Tightening it onto the panel terminal with the insulated screwdriver.",
    "दक्षिण पैनल पर काम",  # 'south' must not match 'दक्ष'
])
def test_allows_neutral_descriptions(text):
    assert guardrails.find_violations(text) == []
    assert guardrails.neutralise(text).text == text


def test_neutralise_keeps_clean_sentences():
    out = guardrails.neutralise("Lug is crimped with a crimping tool. The candidate is competent. Screw is tightened.")
    assert "crimping tool" in out.text and "Screw is tightened" in out.text
    assert "competent" not in out.text.replace(guardrails.NOTICE, "")
    assert out.violations == ["competency_verdict"]


def test_filter_tags():
    clean, v = guardrails.filter_tags(["wire stripper", "competent", "crimping tool"])
    assert clean == ["wire stripper", "crimping tool"] and v == ["competency_verdict"]


def test_demo_fixture_ai_text_is_clean():
    fx = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    texts = [fx["summary"]] + [d["description"] for d in fx["segment_descriptions"]] + [m["rationale"] for m in fx["mappings"]]
    for t in texts:
        assert guardrails.is_clean(t), t

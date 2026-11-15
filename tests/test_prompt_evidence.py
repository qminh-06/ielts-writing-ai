"""Regression tests for exact evidence instructions in grading prompts."""

from ielts_ai.agent.prompts import GRADING_SYSTEM_PROMPT, PROMPT_VERSION, build_regrade_prompt


def test_prompt_requires_verbatim_evidence_including_candidate_errors() -> None:
    exact_instruction = (
        "Evidence quotes MUST be copied EXACTLY from the essay, including the candidate's "
        "grammar and spelling mistakes. Never correct, paraphrase, or alter a quote."
    )
    assert PROMPT_VERSION == "1.2.0"
    assert exact_instruction in GRADING_SYSTEM_PROMPT

    system, _ = build_regrade_prompt(
        prompt_text="Discuss education.",
        essay_text="Students learns together.",
        rubric_context="",
        criterion="GRA",
        examiner_feedback="Please reconsider this criterion.",
    )
    assert exact_instruction in system

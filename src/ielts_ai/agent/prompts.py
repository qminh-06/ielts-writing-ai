"""Prompt templates for IELTS Writing Task 2 grading.

# TODO(A2): Replace placeholder templates with real, tested prompts.
"""

GRADING_SYSTEM_PROMPT = """\
# TODO(A2): Write the system prompt for IELTS Writing Task 2 grading.
You are an expert IELTS Writing Task 2 assessor. Assess the candidate's essay objectively based on official band descriptors for TR, CC, LR, and GRA. Return your assessment formatted as JSON matching the GradingResult schema.
"""

GRADING_USER_TEMPLATE = """\
Assess the following IELTS Writing Task 2 essay.

## Prompt / Task
{prompt_text}

## Essay
<essay>
{essay_text}
</essay>

## Retrieved Rubric Context
{rubric_context}

Provide your assessment as JSON.
"""

REGRADE_USER_TEMPLATE = """\
Re-assess the following criterion based on examiner feedback.

## Criterion to Re-assess
{criterion}

## Examiner Feedback
{examiner_feedback}

## Prompt / Task
{prompt_text}

## Essay
<essay>
{essay_text}
</essay>

## Retrieved Rubric Context
{rubric_context}

Provide your revised assessment as JSON.
"""


def build_grading_prompt(
    prompt_text: str,
    essay_text: str,
    rubric_context: str,
) -> tuple[str, str]:
    """Build system and user prompts for first-time grading.

    # TODO(A2): Finalize prompt content.
    """
    return (
        GRADING_SYSTEM_PROMPT,
        GRADING_USER_TEMPLATE.format(
            prompt_text=prompt_text,
            essay_text=essay_text,
            rubric_context=rubric_context,
        ),
    )


def build_regrade_prompt(
    prompt_text: str,
    essay_text: str,
    rubric_context: str,
    criterion: str,
    examiner_feedback: str,
) -> tuple[str, str]:
    """Build system and user prompts for re-grading a single criterion.

    # TODO(A2): Finalize regrade prompt content.
    """
    return (
        GRADING_SYSTEM_PROMPT,
        REGRADE_USER_TEMPLATE.format(
            criterion=criterion,
            examiner_feedback=examiner_feedback,
            prompt_text=prompt_text,
            essay_text=essay_text,
            rubric_context=rubric_context,
        ),
    )


def format_rubric_context(chunks: list) -> str:
    """Format rubric chunks into a readable string for the prompt."""
    if not chunks:
        return "(No rubric context retrieved)"
    lines = []
    for chunk in chunks:
        criterion = getattr(chunk, "criterion", "?")
        band = getattr(chunk, "band", "?")
        text = getattr(chunk, "text", "")
        source = getattr(chunk, "source", "")
        lines.append(f"[{criterion} Band {band}] {text} (Source: {source})")
    return "\n".join(lines)

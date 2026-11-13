import math
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_validator, model_validator


def calculate_overall_band(bands: list[float]) -> float:
    """Apply IELTS half-up-to-0.5 rounding to a list of criterion bands."""
    if not bands:
        raise ValueError("At least one criterion band is required.")
    return math.floor(sum(bands) / len(bands) * 2 + 0.5) / 2


class Criterion(str, Enum):
    TR = "TR"  # Task Response
    CC = "CC"  # Coherence & Cohesion
    LR = "LR"  # Lexical Resource
    GRA = "GRA"  # Grammatical Range & Accuracy


class EssayStatus(str, Enum):
    pending = "pending"
    ai_done = "ai_done"
    reviewing = "reviewing"
    approved = "approved"
    emailed = "emailed"
    grading_failed = "grading_failed"


class RubricChunk(BaseModel):
    criterion: Criterion
    band: int
    text: str
    source: str


class CriterionScore(BaseModel):
    criterion: Criterion
    band: float  # 0-9, step 0.5
    comment: str
    evidence: list[str]

    @field_validator("band")
    @classmethod
    def band_must_be_valid(cls, v: float) -> float:
        valid = {x / 2 for x in range(0, 19)}  # {0, 0.5, 1.0, ..., 9.0}
        if v not in valid:
            raise ValueError(f"band must be a multiple of 0.5 between 0 and 9, got {v}")
        return v


class GradingResult(BaseModel):
    essay_id: int
    version: int
    criteria: list[CriterionScore]  # exactly 4, one per Criterion
    warnings: list[str]
    retrieved_rubric: list[RubricChunk]
    model: str
    created_at: datetime

    @model_validator(mode="after")
    def validate_criteria(self) -> "GradingResult":
        if len(self.criteria) != 4:
            raise ValueError(f"criteria must contain exactly 4 items, got {len(self.criteria)}")
        seen = {c.criterion for c in self.criteria}
        expected = set(Criterion)
        if seen != expected:
            raise ValueError(
                f"criteria must cover all four Criterion values; "
                f"missing: {expected - seen}, extra: {seen - expected}"
            )
        return self

    @property
    def overall_band(self) -> float:
        """IELTS rounding: floor(mean * 2 + 0.5) / 2."""
        return calculate_overall_band([criterion.band for criterion in self.criteria])


class ReviewDecision(BaseModel):
    essay_id: int
    final_bands: dict[Criterion, float]  # one per criterion
    examiner_comment: str
    action: str  # "accept" | "regrade"
    regrade_criterion: Criterion | None = None
    regrade_feedback: str | None = None

    @model_validator(mode="after")
    def validate_regrade_fields(self) -> "ReviewDecision":
        if self.action == "regrade" and self.regrade_criterion is None:
            raise ValueError("regrade_criterion must be set when action is 'regrade'")
        return self

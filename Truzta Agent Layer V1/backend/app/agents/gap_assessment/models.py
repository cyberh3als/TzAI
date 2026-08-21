"""Pydantic contracts for the gap assessment agent."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GapQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    text: str
    control_ids: list[str] = Field(default_factory=list)
    domain: str | None = None
    is_universal: bool = False
    order: int


class GapAnswer(BaseModel):
    """One question's full transcript: the initial answer plus up to 2 follow-up answers, in order."""

    model_config = ConfigDict(extra="forbid")
    question_id: str
    segments: list[str] = Field(min_length=1)
    answered_at: datetime


class GapFinding(BaseModel):
    """Always 1:1 with the GapQuestion it came from — finding_id == question_id.

    `question_text` and `domain` are denormalised from the question so a findings
    report renders standalone without joining back to the questionnaire.

    `priority` is NOT model-generated — it is computed deterministically from SCF
    catalog fields in priority.py and overwritten after the LLM returns.
    """

    model_config = ConfigDict(extra="forbid")
    finding_id: str
    question_id: str
    question_text: str
    domain: str | None = None
    control_ids: list[str] = Field(default_factory=list)
    summary: str
    status: Literal["open", "closed"]
    priority: Literal["high", "medium", "low"]
    suggestion: str
    created_at: datetime


class GapAssessmentState(BaseModel):
    """Interview progress — lets a page reload resume instead of restarting."""

    model_config = ConfigDict(extra="forbid")
    questions: list[GapQuestion] = Field(default_factory=list)
    answers: list[GapAnswer] = Field(default_factory=list)
    current_question_id: str | None = None
    current_followup_count: int = 0
    # The follow-up text currently awaiting an answer. Held separately from the
    # question list because follow-ups are generated mid-interview, and it must
    # survive a reload or the client would see the original question again.
    pending_prompt: str | None = None
    status: Literal["in_progress", "awaiting_evaluation", "complete"] = "in_progress"

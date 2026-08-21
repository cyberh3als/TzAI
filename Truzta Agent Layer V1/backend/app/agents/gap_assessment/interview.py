"""Drives the gap interview one answer at a time.

The state machine lives here in deterministic code rather than in a conversational
prompt, so the follow-up cap is a hard bound the model cannot argue its way past:

    ask question -> answer -> (maybe follow-up) -> answer -> (maybe follow-up)
                 -> answer -> next question

MAX_FOLLOWUPS is counted per question, not per interview. Once it's reached the
interview advances regardless of how vague the transcript still is; the evaluator
then judges what it has and errs toward "open".

State is persisted after every answer so a page reload resumes mid-interview
instead of restarting.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ...models import ClientMemory
from .followup import generate_followup
from .models import GapAnswer, GapAssessmentState, GapQuestion

MAX_FOLLOWUPS = 2

# Stand-in transcript for a question the interview never reached. Ending an
# interview early must still produce a complete report, so unreached questions are
# assessed as "not in place" rather than omitted — a control nobody confirmed is a
# gap, not an absence of information. Phrased as a real answer so the evaluator
# judges it through the normal path and still writes a specific summary and
# treatment for it.
UNREACHED_ANSWER = "No - this is not in place. The client did not reach this question."


class InterviewStep(BaseModel):
    """What the client should see next."""

    model_config = ConfigDict(extra="forbid")
    kind: Literal["question", "followup", "complete"]
    prompt: str | None = None
    question_id: str | None = None
    domain: str | None = None
    answered: int
    total: int


def start(questions: list[GapQuestion]) -> GapAssessmentState:
    return GapAssessmentState(
        questions=questions,
        answers=[],
        current_question_id=questions[0].question_id if questions else None,
        current_followup_count=0,
        status="in_progress" if questions else "awaiting_evaluation",
    )


def current_step(state: GapAssessmentState) -> InterviewStep:
    """Describe the pending prompt without advancing anything."""
    total = len(state.questions)
    answered = _answered_count(state)
    if state.status != "in_progress" or state.current_question_id is None:
        return InterviewStep(kind="complete", answered=answered, total=total)

    question = _question(state, state.current_question_id)
    is_followup = state.current_followup_count > 0
    return InterviewStep(
        kind="followup" if is_followup else "question",
        # A pending follow-up's text is stored as the last transcript entry when it
        # was issued; a fresh question uses its own text.
        prompt=state.pending_prompt or question.text,
        question_id=question.question_id,
        domain=question.domain,
        answered=answered,
        total=total,
    )


def submit_answer(
    state: GapAssessmentState,
    text: str,
    memory: ClientMemory,
    controls: list[dict],
) -> GapAssessmentState:
    """Record one answer, then either ask a follow-up or move to the next question."""
    if state.status != "in_progress" or state.current_question_id is None:
        return state

    question = _question(state, state.current_question_id)
    _append_segment(state, question.question_id, text)

    if state.current_followup_count < MAX_FOLLOWUPS:
        transcript = _transcript(state, question.question_id)
        by_id = {control["scf_id"]: control for control in controls}
        mapped = [by_id[cid] for cid in question.control_ids if cid in by_id]
        follow_up = generate_followup(question, mapped, memory, transcript)
        if follow_up:
            state.current_followup_count += 1
            state.pending_prompt = follow_up
            return state

    _advance(state)
    return state


def skip(state: GapAssessmentState) -> GapAssessmentState:
    """Move past the current question, recording it as skipped."""
    if state.status != "in_progress" or state.current_question_id is None:
        return state
    if not _transcript(state, state.current_question_id):
        _append_segment(state, state.current_question_id, "[skipped]")
    _advance(state)
    return state


def _advance(state: GapAssessmentState) -> None:
    order = [question.question_id for question in state.questions]
    index = order.index(state.current_question_id) if state.current_question_id in order else -1
    state.current_followup_count = 0
    state.pending_prompt = None
    if index < 0 or index + 1 >= len(order):
        state.current_question_id = None
        state.status = "awaiting_evaluation"
    else:
        state.current_question_id = order[index + 1]


def _question(state: GapAssessmentState, question_id: str) -> GapQuestion:
    for question in state.questions:
        if question.question_id == question_id:
            return question
    raise KeyError(f"Unknown question {question_id!r}")


def _transcript(state: GapAssessmentState, question_id: str) -> list[str]:
    for answer in state.answers:
        if answer.question_id == question_id:
            return list(answer.segments)
    return []


def _append_segment(state: GapAssessmentState, question_id: str, text: str) -> None:
    for answer in state.answers:
        if answer.question_id == question_id:
            answer.segments.append(text)
            answer.answered_at = datetime.now(timezone.utc)
            return
    state.answers.append(GapAnswer(
        question_id=question_id,
        segments=[text],
        answered_at=datetime.now(timezone.utc),
    ))


def _answered_count(state: GapAssessmentState) -> int:
    """Questions fully done — the in-flight one doesn't count until we move past it."""
    done = {answer.question_id for answer in state.answers}
    if state.current_question_id in done:
        done.discard(state.current_question_id)
    return len(done)


def fill_unreached(state: GapAssessmentState) -> list[GapAnswer]:
    """Answers for every control-backed question, assuming "no" for unreached ones.

    Universal questions are left out: they map to no control, so a finding derived
    from one anchors to nothing. Answered universal questions are still included.
    """
    answered = {answer.question_id for answer in state.answers}
    now = datetime.now(timezone.utc)
    filled = list(state.answers)
    for question in state.questions:
        if question.question_id in answered or question.is_universal:
            continue
        filled.append(GapAnswer(
            question_id=question.question_id,
            segments=[UNREACHED_ANSWER],
            answered_at=now,
        ))
    return filled

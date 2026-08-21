"""Turns a completed interview transcript into GapFindings.

One LLM call per question (they are independent, so they run concurrently), each
judging that question's control cluster as a single finding. The model decides
only `summary`, `status` and `suggestion`; `priority` is computed deterministically
from the SCF catalog afterwards and is never taken from the model — see priority.py.

Findings are always 1:1 with questions, so coverage needs no reconciliation pass:
every question yields exactly one finding, and a failed call degrades to an open
finding rather than dropping the question silently.
"""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from openai import OpenAIError

from ...models import ClientMemory
from .business_size import get_consideration
from .client import FOLLOWUP_MODEL, QUESTION_MODEL, get_client
from .models import GapAnswer, GapFinding, GapQuestion
from .priority import build_priority_map, priority_for
from .prompts import GAP_EVALUATION_PROMPT

logger = logging.getLogger(__name__)

# Same reasoning-model trap as questions.py: hidden reasoning is billed against this
# budget, so a tight cap returns `content=None` (reasoning consumed it all) rather
# than a parse error. Measured 2/38 questions failing this way at 4096.
_MAX_TOKENS = 16000
_MAX_PARALLEL_QUESTIONS = int(os.environ.get("GAP_EVALUATION_CONCURRENCY", "8"))

# Stand-in transcript for a question the client never answered. The prompt has an
# explicit rule for this exact string.
SKIPPED = "[skipped]"


def evaluate_gaps(
    memory: ClientMemory,
    controls: list[dict],
    questions: list[GapQuestion],
    answers: list[GapAnswer],
) -> list[GapFinding]:
    by_control = {control["scf_id"]: control for control in controls}
    by_question = {answer.question_id: answer for answer in answers}
    priority_map = build_priority_map(controls)
    client_context = _client_context(memory)

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_QUESTIONS) as pool:
        judgments = list(pool.map(
            lambda question: _judge(question, by_question.get(question.question_id),
                                    by_control, memory, client_context),
            questions,
        ))
    logger.info(
        "Evaluated %d gap questions in %.1fs (concurrency %d)",
        len(questions), time.monotonic() - started, _MAX_PARALLEL_QUESTIONS,
    )

    created_at = datetime.now(timezone.utc)
    return [
        GapFinding(
            finding_id=question.question_id,
            question_id=question.question_id,
            question_text=question.text,
            domain=question.domain,
            control_ids=question.control_ids,
            summary=judgment["summary"],
            status=judgment["status"],
            priority=priority_for(question.control_ids, priority_map),
            suggestion=judgment["suggestion"],
            created_at=created_at,
        )
        for question, judgment in zip(questions, judgments)
    ]


def _judge(
    question: GapQuestion,
    answer: GapAnswer | None,
    by_control: dict[str, dict],
    memory: ClientMemory,
    client_context: dict,
) -> dict:
    transcript = list(answer.segments) if answer else [SKIPPED]
    payload = {
        "question": question.text,
        "controls": [
            _control_payload(by_control[cid], memory)
            for cid in question.control_ids
            if cid in by_control
        ],
        "client": client_context,
        "answer_transcript": transcript,
    }
    # Retried on the secondary model rather than the same one: the observed failure
    # is a specific prompt reliably drawing an empty completion from the primary
    # model, which re-rolling the identical call does not fix.
    for model in (QUESTION_MODEL, FOLLOWUP_MODEL):
        try:
            return _call(model, payload)
        except (OpenAIError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            logger.warning(
                "Gap evaluation for %s failed on %s: %s",
                question.question_id, model, error,
            )

    logger.warning("Gap evaluation for %s failed on all models, defaulting to open",
                   question.question_id)
    # Fail open, never closed: an unevaluated control must surface for review
    # rather than be silently reported as satisfied.
    return {
        "summary": "This area could not be assessed automatically and needs manual review.",
        "status": "open",
        "suggestion": "Review this question manually with the client.",
    }


def _call(model: str, payload: dict) -> dict:
    response = get_client().chat.completions.create(
        model=model,
        max_tokens=_MAX_TOKENS,
        messages=[
            {"role": "system", "content": GAP_EVALUATION_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty content")
    result = json.loads(content)
    status = result["status"]
    if status not in ("open", "closed"):
        raise ValueError(f"Unexpected status {status!r}")
    return {
        "summary": str(result["summary"]),
        "status": status,
        "suggestion": str(result["suggestion"]),
    }


def _control_payload(control: dict, memory: ClientMemory) -> dict:
    """Deliberately narrow: scr_cmm (the 5-level maturity prose) is excluded — it is
    the bulk of a control record but adds only jargon to this judgment."""
    return {
        "scf_id": control["scf_id"],
        "control_question": control.get("control_question", ""),
        "description": control.get("description", ""),
        "weight": control.get("weight", ""),
        "business_size_guidance": get_consideration(control, memory.organization.employee_range),
        "evidence_codes": control.get("evidence_request_list_erl", ""),
    }


def _client_context(memory: ClientMemory) -> dict:
    return {
        "organization": memory.organization.model_dump(mode="json"),
        "applicability": memory.applicability.model_dump(mode="json"),
        "technology": memory.technology.model_dump(mode="json"),
    }

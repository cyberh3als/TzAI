"""Decides whether one more clarifying question is needed for the current topic.

The 2-follow-up cap is enforced by the caller (interview.py), not here and not by
the prompt — this module only answers "is there enough detail yet?". Keeping the
cap in deterministic code means a talkative model can never stretch an interview
past its bound.

Uses the cheaper/faster model tier: this is the high-frequency call in the agent,
running up to three times per question, and it only makes a binary-ish judgement.
"""

import json
import logging

from openai import OpenAIError

from ...models import ClientMemory
from .business_size import get_consideration
from .client import FOLLOWUP_MODEL, get_client
from .models import GapQuestion
from .prompts import FOLLOWUP_JUDGMENT_PROMPT

logger = logging.getLogger(__name__)

# Measured against deepseek-v4-flash: 8000 -> 8.6s, 2000 -> 5.9s, and the call only
# ever emits a one-line question (262-352 completion tokens observed). 2000 keeps
# headroom over that while cutting ~30% off the client's wait between questions.
_MAX_TOKENS = 2000


def generate_followup(
    question: GapQuestion,
    controls: list[dict],
    memory: ClientMemory,
    transcript: list[str],
) -> str | None:
    """Return one follow-up question, or None when the transcript is already sufficient."""
    if not controls:
        # The judge is asked "is this enough to assess the mapped controls?" — with
        # none mapped it can only answer yes, so the call is a guaranteed no-op.
        # Universal questions hit this path; skipping it saves ~6s per answer.
        return None

    payload = {
        "question": question.text,
        "controls": [
            {
                "scf_id": control["scf_id"],
                "control_question": control.get("control_question", ""),
                "description": control.get("description", ""),
                "business_size_guidance": get_consideration(control, memory.organization.employee_range),
            }
            for control in controls
        ],
        "client": {
            "organization": memory.organization.model_dump(mode="json"),
            "technology": memory.technology.model_dump(mode="json"),
        },
        "answer_so_far": transcript,
    }
    try:
        response = get_client().chat.completions.create(
            model=FOLLOWUP_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": FOLLOWUP_JUDGMENT_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Model returned empty content")
        follow_up = json.loads(content).get("follow_up")
        if follow_up is None or not str(follow_up).strip():
            return None
        return str(follow_up).strip()
    except (OpenAIError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        # Failing closed (no follow-up) keeps the interview moving; the evaluator
        # will judge on whatever detail exists and err toward "open" if it's thin.
        logger.warning("Follow-up judgment failed for %s, continuing: %s", question.question_id, error)
        return None

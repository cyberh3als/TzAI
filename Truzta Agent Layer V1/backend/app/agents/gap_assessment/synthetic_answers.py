"""Synthetic interview answers for testing the evaluation pipeline without a human.

Test-support only — nothing in the request path imports this. It exists so gap
findings can be exercised end-to-end before the chat UI is built, and so a
worst-case baseline ("nothing is in place") can be regenerated deterministically.

Two modes:
    baseline  every question answered negatively — the expected result is that
              essentially every finding comes back `open`, which makes it a sharp
              test of the evaluator: any `closed` finding here is a false negative
              worth investigating.
    random    yes/no chosen per question from a seeded RNG, for a realistic mix.

Universal questions are skipped in both modes (they carry no control_ids, so they
produce findings that map to nothing).
"""

import random
from datetime import datetime, timezone

from .models import GapAnswer, GapQuestion

NEGATIVE_ANSWERS = [
    "No, we do not have this in place.",
    "Not present.",
    "Not practiced.",
    "No — we have never set this up.",
    "No, nothing formal exists for this.",
]

POSITIVE_ANSWERS = [
    "Yes, we have this documented and in place.",
    "Yes — this is implemented and reviewed annually.",
    "Yes, this is standard practice for us and is written down.",
]


def build_answers(
    questions: list[GapQuestion],
    mode: str = "baseline",
    seed: int = 20260821,
    skip_universal: bool = True,
) -> list[GapAnswer]:
    rng = random.Random(seed)
    answered_at = datetime.now(timezone.utc)

    answers: list[GapAnswer] = []
    for question in questions:
        if skip_universal and question.is_universal:
            continue
        if mode == "baseline":
            text = rng.choice(NEGATIVE_ANSWERS)
        elif mode == "random":
            pool = POSITIVE_ANSWERS if rng.random() < 0.5 else NEGATIVE_ANSWERS
            text = rng.choice(pool)
        else:
            raise ValueError(f"Unknown mode {mode!r} — expected 'baseline' or 'random'")
        answers.append(GapAnswer(
            question_id=question.question_id,
            segments=[text],
            answered_at=answered_at,
        ))
    return answers

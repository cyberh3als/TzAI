"""Generates the gap-assessment questionnaire from a client's applicable controls.

Groups controls by scf_domain (one LLM call per domain — keeps each call's
context small and reliable), asks the model to cluster them into interview
questions, then deterministically validates that every control_id survived.
The model proposes the clustering; this module enforces coverage.
"""

import json
import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAIError

from ...models import ClientMemory
from .client import QUESTION_MODEL, get_client
from .models import GapQuestion
from .prompts import QUESTION_GENERATION_PROMPT
from .scope import in_scope
from .universal_questions import UNIVERSAL_QUESTIONS

logger = logging.getLogger(__name__)

# Target band for total question count relative to total applicable controls —
# a design constraint, not a hard contract, so it's only ever logged.
_TARGET_RATIO_LOW = 0.7
_TARGET_RATIO_HIGH = 1.0

# deepseek's OpenRouter provider doesn't support strict json_schema mode yet,
# only json_object — the expected shape is described in the prompt text
# (see prompts/gap_assessment/question_generation.md) and checked by hand
# below rather than enforced by the API.
# Generous because both models are reasoning models: hidden reasoning is billed
# against the same budget as the visible answer, so a tight cap truncates the
# JSON mid-string and silently drops the whole domain to the fallback path.
_MAX_TOKENS = 16000

# Large domains are split across several calls. Data Privacy carries 22 controls
# for a GDPR/PDPA client, which overran the old cap and produced exactly that
# silent fallback. Smaller batches also parallelise better.
_MAX_CONTROLS_PER_CALL = 10

# Domain calls are independent — nothing in _generate_for_domain touches shared
# state, and coverage is validated deterministically afterwards — so they run
# concurrently. Measured sequentially at ~22s per domain, which put a 23-domain
# client (SOC 2) at ~8.5 minutes before a questionnaire appeared.
# Kept modest to stay clear of OpenRouter rate limits; tune via env var.
_MAX_PARALLEL_DOMAINS = int(os.environ.get("GAP_QUESTION_CONCURRENCY", "8"))


def generate_questions(memory: ClientMemory, controls: list[dict]) -> list[GapQuestion]:
    """Build the full questionnaire: universal questions + one clustered set per control domain."""
    controls = in_scope(controls)
    raw: list[dict] = [
        {"text": item["text"], "control_ids": [], "domain": None, "is_universal": True}
        for item in UNIVERSAL_QUESTIONS
    ]

    by_domain: dict[str, list[dict]] = defaultdict(list)
    for control in controls:
        by_domain[control.get("scf_domain", "Uncategorized")].append(control)

    memory_context = _memory_context(memory)
    batches = _batch(by_domain)
    started = time.monotonic()
    # pool.map preserves input order, so the questionnaire stays grouped by
    # domain in catalog order regardless of which call finishes first.
    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_DOMAINS) as pool:
        per_batch = list(pool.map(
            lambda batch: _generate_for_domain(batch[0], batch[1], memory_context),
            batches,
        ))
    logger.info(
        "Generated gap questions for %d domains in %d batches in %.1fs (concurrency %d)",
        len(by_domain), len(batches), time.monotonic() - started, _MAX_PARALLEL_DOMAINS,
    )

    for (domain, _), items in zip(batches, per_batch):
        for item in items:
            raw.append({
                "text": item["text"],
                "control_ids": item["control_ids"],
                "domain": domain,
                "is_universal": False,
            })

    raw = _ensure_coverage(raw, controls)
    _log_coverage_ratio(raw, controls)

    return [
        GapQuestion(question_id=f"gq-{index:04d}", order=index, **item)
        for index, item in enumerate(raw)
    ]


def _batch(by_domain: dict[str, list[dict]]) -> list[tuple[str, list[dict]]]:
    """Flatten domains into LLM-call-sized batches, preserving domain order."""
    batches: list[tuple[str, list[dict]]] = []
    for domain, domain_controls in by_domain.items():
        for start in range(0, len(domain_controls), _MAX_CONTROLS_PER_CALL):
            batches.append((domain, domain_controls[start:start + _MAX_CONTROLS_PER_CALL]))
    return batches


def _generate_for_domain(domain: str, controls: list[dict], memory_context: dict) -> list[dict]:
    payload = {
        "domain": domain,
        "controls": [
            {
                "scf_id": control["scf_id"],
                "control_question": control.get("control_question", ""),
                "description": control.get("description", ""),
            }
            for control in controls
        ],
        "client_memory": memory_context,
    }
    try:
        client = get_client()
        response = client.chat.completions.create(
            model=QUESTION_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": QUESTION_GENERATION_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        items = result["questions"]
        return [{"text": item["text"], "control_ids": list(item["control_ids"])} for item in items]
    except (OpenAIError, json.JSONDecodeError, KeyError, TypeError) as error:
        logger.warning(
            "Gap question generation failed for domain %r, falling back to 1:1 questions: %s",
            domain, error,
        )
        return [
            {"text": _fallback_text(control), "control_ids": [control["scf_id"]]}
            for control in controls
        ]


def _fallback_text(control: dict) -> str:
    """Templated stand-in used when a batch's LLM call fails.

    Deliberately not the raw SCF `control_question`: those are multi-part,
    jargon-heavy and open-ended (a single one runs to seven numbered clauses),
    which is exactly the phrasing the questionnaire is meant to avoid. The
    control name in a binary template stays consistent with everything else.
    """
    name = (control.get("scf_control_name") or "").strip()
    if not name:
        return f"Is the control {control['scf_id']} in place at your organisation?"
    return f"Do you have {name[0].lower() + name[1:]} in place at your organisation?"


def _ensure_coverage(raw_questions: list[dict], controls: list[dict]) -> list[dict]:
    """Append a fallback 1:1 question for any control_id the model dropped."""
    covered = {control_id for item in raw_questions for control_id in item["control_ids"]}
    for control in controls:
        control_id = control["scf_id"]
        if control_id not in covered:
            raw_questions.append({
                "text": control.get("control_question") or f"Is the following control in place: {control_id}?",
                "control_ids": [control_id],
                "domain": control.get("scf_domain"),
                "is_universal": False,
            })
    return raw_questions


def _log_coverage_ratio(raw_questions: list[dict], controls: list[dict]) -> None:
    if not controls:
        return
    ratio = len(raw_questions) / len(controls)
    if not (_TARGET_RATIO_LOW <= ratio <= _TARGET_RATIO_HIGH):
        logger.warning(
            "Gap questionnaire has %d questions for %d applicable controls (ratio %.2f), "
            "outside the %.0f%%-%.0f%% target band",
            len(raw_questions), len(controls), ratio,
            _TARGET_RATIO_LOW * 100, _TARGET_RATIO_HIGH * 100,
        )


def _memory_context(memory: ClientMemory) -> dict:
    return {
        "organization": memory.organization.model_dump(mode="json"),
        "applicability": memory.applicability.model_dump(mode="json"),
        "technology": memory.technology.model_dump(mode="json"),
        "facts": [fact.model_dump(mode="json") for fact in memory.facts],
    }

"""LLM-assisted normalization of the technology & infrastructure profile.

Input/output contract: an object keyed by exactly TECHNOLOGY_FIELDS, each a
string or null. The model proposes; nothing here lets it invent a field,
change the shape, or return unvalidated text — the response is checked by
hand against that exact key set, and callers still pass the result through
the TechnologyProfile Pydantic model before it's used.

Uses a deepseek/* model routed through OpenRouter. Originally this used
OpenAI's gpt-4.1-mini as a deliberate one-off exception (every other
LLM-touching part of this codebase defaults to Claude); it was switched to
deepseek because this OpenRouter account's allowed-providers setting
(openrouter.ai/settings/privacy) currently permits only the `deepseek`
provider — an openai/* or anthropic/* model id 404s outright regardless of
API key validity. If the account's allowed providers are widened later,
MODEL is the only thing that needs to change.

deepseek's OpenRouter provider doesn't support strict `json_schema`
response_format yet, only the looser `json_object` mode — so the expected
shape is described in the prompt and validated by hand after parsing
(exact key set, right types) rather than enforced by the API. It's also a
reasoning model (spends completion tokens on hidden reasoning before the
visible answer), hence the generous max_tokens.

Never invents information. Falls back to deterministic phrase-based
normalization (text_normalize.normalize_text) on any API failure — missing
key, network error, a routing/model error from OpenRouter, or a malformed/
incomplete response — so an LLM outage degrades gracefully instead of
blocking onboarding.
"""

import json
import logging
import os

from openai import OpenAIError
from openai import OpenAI

from ..text_normalize import normalize_text

TECHNOLOGY_FIELDS = (
    "identity_provider",
    "device_management",
    "endpoint_protection",
    "password_manager",
    "cloud_infrastructure",
    "network_security",
    "vulnerability_management",
    "patch_management",
    "backup_recovery",
    "email_collaboration",
    "logging_siem",
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("TECHNOLOGY_NORMALIZER_MODEL", "deepseek/deepseek-v4-flash")
_MAX_TOKENS = 2048

SYSTEM_PROMPT = """you are a cybersecurity expert tasked with normalizing a client's free-text answers about their technology and security infrastructure for a compliance platform's client-memory record.

For each field, given the client's raw typed answer:
- If the answer indicates they don't know, don't have one, or gave no real answer (e.g. "not sure", "none", "n/a", "idk", "no"), return null.
- If the answer names or clearly implies a real product or vendor, return that product's standard name (e.g. "in tune" -> "Microsoft Intune", "1pw" -> "1Password").
- If the answer is already clear and specific, return it with only minor cleanup (typos, casing) — do not shorten or reinterpret real content.
- Never invent details the client did not state. If you are not confident what an answer refers to, return it unchanged rather than guessing.

Return a JSON object with exactly these keys, each a string or null: identity_provider, device_management, endpoint_protection, password_manager, cloud_infrastructure, network_security, vulnerability_management, patch_management, backup_recovery, email_collaboration, logging_siem."""

logger = logging.getLogger(__name__)


def normalize_technology_profile(raw: dict[str, str | None]) -> dict[str, str | None]:
    """Best-effort LLM normalization; falls back to deterministic matching on failure."""
    try:
        client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.environ.get("OPENROUTER_API_KEY"))
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({field: raw.get(field) for field in TECHNOLOGY_FIELDS})},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        normalized: dict[str, str | None] = {}
        for field in TECHNOLOGY_FIELDS:
            value = result[field]
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{field} must be a string or null, got {type(value)!r}")
            normalized[field] = value
        return normalized
    except (OpenAIError, json.JSONDecodeError, KeyError, TypeError) as error:
        logger.warning("Technology profile LLM normalization failed, falling back to deterministic matching: %s", error)
        return {field: normalize_text(raw.get(field)) for field in TECHNOLOGY_FIELDS}

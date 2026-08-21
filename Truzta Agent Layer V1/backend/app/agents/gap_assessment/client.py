"""Shared OpenRouter client setup for the gap assessment agent.

Same OpenRouter-via-the-openai-SDK pattern as agents/technology_normalizer.py.
Two model tiers, both configurable via env vars: a stronger model for the two
calls that run once per client (question generation, gap evaluation), and a
cheap/fast model for the high-frequency call (follow-up judgment, up to 3x
per question).

Defaults are deepseek/* models: this OpenRouter account's allowed-providers
setting (openrouter.ai/settings/privacy) currently permits only the
`deepseek` provider, so an openai/* or anthropic/* model id 404s outright
regardless of API key validity. deepseek-v4-pro/flash are also priced well
within a tight budget. If the account's allowed providers are widened later,
these two env vars are the only thing that needs to change.

Both models are reasoning models (they spend completion tokens on hidden
reasoning before the visible answer), so calls need a generous max_tokens,
and neither supports strict `json_schema` response_format yet — only the
looser `json_object` mode, so the expected shape is described in the prompt
text and validated by hand after parsing rather than enforced by the API.
"""

import os

from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

QUESTION_MODEL = os.environ.get("GAP_QUESTION_MODEL", "deepseek/deepseek-v4-pro")
FOLLOWUP_MODEL = os.environ.get("GAP_FOLLOWUP_MODEL", "deepseek/deepseek-v4-flash")


def get_client() -> OpenAI:
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=os.environ.get("OPENROUTER_API_KEY"))

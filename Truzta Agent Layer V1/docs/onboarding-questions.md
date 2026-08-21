# Onboarding questions

Source of truth: [`frontend/src/Onboarding.jsx`](../frontend/src/Onboarding.jsx) (`questionGroups`). This document is a
human-readable mirror of that array — if you change the questions in code, update this file in the same change.

Each question's `id` is also the field name in `OnboardingSubmission`
([`backend/app/models.py`](../backend/app/models.py)), so the mapping from question to stored data is 1:1.

## 1. Compliance target

| # | Question | Type | Options | Required | Subtext |
|---|---|---|---|---|---|
| 1 | Which compliance frameworks are you working towards? | Multi-select | Loaded from `GET /api/frameworks` (ISO 27001, SOC 2, HIPAA Administrative, GDPR, Singapore PDPA, Malaysia PDPA, PCI DSS 4.0.1) | Yes | Select every framework you need to comply with — you can pick more than one. |

## 2. Organization

| # | Question | Type | Options | Required | Subtext |
|---|---|---|---|---|---|
| 2 | What is your organisation called? | Free text | — | Yes | Used to identify your workspace. |
| 3 | How many people work at the organisation? | Single-select | `1-9`, `10-49`, `50-249`, `250-999`, `1000+` | Yes | Include full-time, part-time, and contracted staff. |
| 4 | What industry best describes your business? | Free text | — | No | e.g. Fintech, Healthcare, E-commerce, Professional services |
| 5 | Which countries do you operate in, and/or serve customers in? | Free text (comma-separated list) | — | Yes | This can affect which country-specific privacy laws (e.g. GDPR, PDPA) apply to you. |
| 6 | What are the departments in your organisation? | Free text (comma-separated list) | — | No | e.g. Engineering, Customer Support, Finance |

## 3. Applicability

These three answers gate which SCF controls are included — see [`backend/app/control_catalog.py`](../backend/app/control_catalog.py) (`select_controls`) and [`backend/app/control_tagging.py`](../backend/app/control_tagging.py).

| # | Question | Type | Options | Required | Subtext | Filtering effect |
|---|---|---|---|---|---|---|
| 7 | What sensitive data do you handle? | Multi-select | `Personal data`, `Health data`, `Payment card data`, `Employee data`, `Financial data`, `None / unsure` | Yes | Select everything that applies — this determines which data-specific controls are relevant to you. | Recorded in memory. Not currently used to drop controls — the SCF text has no reliable payment-card/health-data-only signal (see decision below). |
| 8 | Does your organisation build or maintain software? | Yes / No | — | Yes | Includes any in-house development — your core product or internal tools. | Drops every `development`-tagged control when "No". Takes priority over the `physical` tag on controls that carry both. |
| 9 | How does your team work? | Single-select | `Fully on-site`, `Fully remote`, `Hybrid` | Yes | Determines whether physical security controls (badges, visitor logs, office access) apply to you. | Drops every `physical`-tagged control when "Fully remote". |

## 4. Technology & infrastructure profile

Memory only — these answers are stored on the client's `technology` profile for future agents (e.g. gap assessment) to read; they do not filter the control list.

| # | Question | Type | Required | Subtext |
|---|---|---|---|---|
| 10 | What manages employee identities and access? | Free text | No | e.g. Microsoft Entra ID, Okta, Google Cloud Identity — include SSO, MFA, admin access if relevant. |
| 11 | Are company laptops and phones centrally managed? | Free text | No | e.g. Microsoft Intune, Endpoint Central, Zoho UEM — or "None". |
| 12 | What protects employee laptops and servers? | Free text | No | e.g. Microsoft Defender, SentinelOne, Sophos |
| 13 | Do employees use a password manager? | Free text | No | e.g. 1Password, Bitwarden, or an enterprise password manager — or "None". |
| 14 | What cloud infrastructure do you run, and how are production and development environments separated? | Free text (textarea) | No | e.g. AWS, GCP, Azure — describe prod/dev separation if any. |
| 15 | How is your corporate and production network protected? | Free text | No | e.g. firewalls, VPNs, Palo Alto, Fortinet, Cisco, Cloudflare Access |
| 16 | What tools do you use for vulnerability scanning and remediation? | Free text | No | e.g. Tenable, Nessus, Qualys, Microsoft Defender Vulnerability Management — or "None". |
| 17 | How are operating systems and applications patched? | Free text | No | e.g. Intune, ManageEngine, NinjaOne — include frequency if known. |
| 18 | What systems and data are backed up, and how often? | Free text (textarea) | No | Include backup frequency and recovery time objective if known. |
| 19 | What platform handles company email and document collaboration? | Free text | No | e.g. Microsoft 365, Google Workspace — note MFA / email security if known. |
| 20 | Where do your security logs go? | Free text | No | e.g. Microsoft Sentinel, Splunk Enterprise Security, Google SecOps — or "None". |

## Answer normalization

**`industry` (question 4)** is checked against a fixed phrase list in
[`backend/app/text_normalize.py`](../backend/app/text_normalize.py) (`NO_ANSWER_PHRASES`) — "not sure", "none",
"n/a", "idk", "don't know", "no", "tbd", etc. A match, or an empty/whitespace-only string, is stored as `null`
instead of the literal text. Fixed string match, no model call.

**The technology & infrastructure profile (questions 10–20)** goes through an LLM call instead —
[`backend/app/agents/technology_normalizer.py`](../backend/app/agents/technology_normalizer.py), using a `deepseek/*`
model routed through OpenRouter (currently `deepseek/deepseek-v4-flash`, configurable via `TECHNOLOGY_NORMALIZER_MODEL`).
This started as OpenAI's `gpt-4.1-mini` — a deliberate exception to defaulting to Claude — but this OpenRouter
account's allowed-providers setting (openrouter.ai/settings/privacy) currently permits only the `deepseek` provider,
so an `openai/*` or `anthropic/*` model id 404s regardless of API key validity. It does two things a fixed phrase
list can't: detects "no answer" the same way, and canonicalizes shorthand into the real product name — "in tune" →
"Microsoft Intune", "1pw" → "1Password". deepseek's OpenRouter provider doesn't support strict `json_schema`
response_format yet, only the looser `json_object` mode, so the expected shape (exactly the 11 known fields,
string-or-null) is described in the prompt and validated by hand after parsing instead — and the result still
passes through the `TechnologyProfile` Pydantic model before use, so the model still only proposes. On any API
failure (no key configured, network error, malformed/incomplete response) it falls back to the same deterministic
phrase list used for `industry`, so a model outage degrades onboarding rather than blocking it.

**Audit trail:** the client's raw, unedited answer for every non-blank technology field is also stored as a
`MemoryFact` (`key: "{field}_raw_answer"`, `source: "onboarding"`) alongside the normalized value in `technology.*`.
If the LLM ever mis-reads an answer, the original text is still in memory to check against.

**Requires `OPENAI_API_KEY`** in the backend process's environment. Without it, every submission silently uses the
deterministic fallback — canonicalization is skipped, but no-answer detection and onboarding itself still work.

Required questions (frameworks, organization name, employee range, countries, the three applicability-gate
questions) are not normalized this way — they're constrained to real values by their input type, so there's no
"not sure" text to catch.

## Fields dropped from earlier drafts

`compliance_driver`, `target_date`, `compliance_owner`, and `annual_budget` were asked in an earlier version of this
flow and have been removed — they added collection overhead without informing control selection or memory that
another agent could act on.

## Known gaps / open decisions

- **No `payment-card` or `health-data` tag.** Investigated during the tagging pass: the SCF control text is written
  generically, so there's no keyword signal (0 hits for "cardholder", "PHI", "health record", etc. across all 834
  controls). The best proxy — "maps exclusively to PCI DSS" — found 122 candidate controls, but the HIPAA equivalent
  found only 1, and that one wasn't actually health-specific. Decision: skip both tags for now rather than tag
  inaccurately; question 7 stays memory-only until there's a real signal to filter on.
- Questions 10–20 may end up duplicating what a future gap-assessment agent asks. Not resolved yet — see the
  `source` field on `MemoryFact` in `models.py`, which already distinguishes `onboarding` facts from
  `gap_assessment` facts so a later agent can check existing memory before re-asking.

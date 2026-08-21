# Truzta Agent Layer

React + Python/FastAPI scaffolding for an SMB-focused GRC platform. This stage implements onboarding and human-readable client memory only. Gap, risk, and policy agents are intentionally not implemented until their contracts are approved.

## Structure

```text
frontend/                 React onboarding application
backend/app/
  main.py                 FastAPI routes and app setup
  models.py               All current Pydantic data contracts
  onboarding.py           Onboarding workflow: memory + deterministic control selection
  memory.py               YAML client-memory + JSON control-list persistence
  control_catalog.py      Read-only SCF queries and control selection
  control_tagging.py      Deterministic applicability tags (development, physical)
  text_normalize.py       Deterministic "no answer" phrase matching
  agents/
    technology_normalizer.py  LLM-assisted normalization of the technology profile (OpenRouter)
  prompts/                Reserved for editable, versioned prompts
data/
  catalog/
    scf_controls.json     Working copy of the SCF control universe, tagged in place
    relationships.json    Deterministic relationship data
  client-memory/          Human-readable per-client YAML, plus a sibling {client_id}.controls.json
  schemas/                JSON Schemas for relationship data
Small SCF JSON Master/    Original approved SCF-derived source data (do not edit; data/catalog/scf_controls.json is the copy the app reads and tags)
```

## Run locally

Backend:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Frontend (a second terminal):

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. FastAPI documentation is available at `http://localhost:8000/docs`.

## Why YAML for client memory?

YAML works well for this prototype because a developer can read, diff, and correct it. Every file is validated through the `ClientMemory` Pydantic model when loaded. Writes are atomic and the model contains a version number for future optimistic concurrency checks.

YAML should remain a persistence adapter, not the domain model. For production, use PostgreSQL for tenant isolation, concurrency, querying, encryption controls, and audit history. YAML also has whitespace pitfalls, so only `yaml.safe_load` and `yaml.safe_dump` are used.

Client YAML contains durable facts, not chat transcripts or hidden reasoning. Learned facts record their source and confidence. Generated client files are ignored by Git; `example.yaml` documents the shape.

## Deterministic relationship catalog

`data/catalog/relationships.json` is the future source for explicit connections among controls, framework requirements, evidence types, and policies. It begins empty because relationships should not be invented. Each future record must include provenance and lifecycle status and validate against `data/schemas/relationship.schema.json`.

Agents should request changes through a deterministic service that validates identifiers, relationship types, duplicates, provenance, and authorization. Agents should never directly rewrite catalog files or decide mappings solely through a prompt.

## Current API

- `GET /api/health`
- `GET /api/frameworks`
- `POST /api/clients` — runs onboarding: validates the submission, saves client memory, computes applicable controls, persists them to `data/client-memory/{client_id}.controls.json`, and returns `{ client, applicable_controls }`
- `GET /api/clients`
- `GET /api/clients/{client_id}`
- `GET /api/clients/{client_id}/controls` — returns the persisted control list; if a client predates this file (or it's missing), computes it once from the stored profile and writes it before returning

No assessment endpoint exists at this stage.

## Onboarding agent

The onboarding agent (`backend/app/onboarding.py`, invoked via `POST /api/clients`) turns a client's answers into two persisted artifacts: durable client memory and an organization-specific control list.

**Inputs**

- The onboarding submission (`OnboardingSubmission` in `models.py`) — 20 questions across compliance target, organization profile, three applicability-gate answers, and 11 free-text technology/infrastructure answers.
- The SCF control catalog — see "Where the input controls come from" below.

**Where the input controls come from**

`data/catalog/scf_controls.json` — 834 unique controls across 7 frameworks (ISO 27001, SOC 2, HIPAA Administrative, GDPR, Singapore PDPA, Malaysia PDPA, PCI DSS 4.0.1). It's a copy of the approved source data in `Small SCF JSON Master/`, tagged in place with the `development`/`physical` applicability tags described below. This file is never hand-edited; only `control_tagging.py` writes to it, and only to add tags.

**What questions are asked**

20 questions in 4 groups: compliance target (which frameworks), organization profile (name, size, industry, countries, departments), three applicability gates (sensitive data handled, does the org build software, work model — these three drive control filtering), and 11 free-text technology/infrastructure questions (identity provider, device management, endpoint protection, and so on — memory only, don't filter controls). Full question text, input types, and the reasoning behind each: `docs/onboarding-questions.md`.

**Process**

1. Validates the selected frameworks against the catalog's known framework list.
2. Normalizes free text — `industry` and general "no answer" phrasing (not sure/none/idk/etc.) via deterministic phrase matching; the 11 technology fields via an LLM call that also canonicalizes shorthand into real product names, falling back to the same deterministic matching on failure. Detail: "Technology profile normalization" below.
3. Builds and saves the `ClientMemory` record, including a `MemoryFact` audit trail of each technology answer's raw, pre-normalization text.
4. Deterministically selects the controls applicable to this client. Detail: "Control selection" below.
5. Persists the selected controls alongside the client memory.

**Outputs**

- `ClientMemory` — durable organization profile, compliance target, applicability answers, technology profile, and fact audit trail.
- The organization-specific applicable control list — full SCF detail per control, plus which of the client's frameworks each one matched.
- Both are returned together from `POST /api/clients` as `{ client, applicable_controls }`.

**Where the output is stored**

- `data/client-memory/{client_id}.yaml` — the client memory.
- `data/client-memory/{client_id}.controls.json` — the applicable control list (computed once at onboarding; for any client that predates this, computed and cached on first request instead).

### Control selection

`control_catalog.select_controls` is the onboarding agent's deterministic filtering step. A control is included when it is applicable to at least one of the client's selected frameworks, then excluded if it carries a tag whose condition the client fails:

- `development` — dropped when the client does not build or maintain software. Takes priority: a control tagged both `development` and `physical` is dropped whenever the client fails the development gate, regardless of its physical-premises answer.
- `physical` — dropped when the client's work model is "Fully remote".

Tags are computed once by `control_tagging.py` from stable SCF fields (domain, control ID)—never inferred from free text at runtime—and cached on `data/catalog/scf_controls.json` via a `tagging_version` stamp in its metadata. Bump `TAGGING_VERSION` when the rules change; the next catalog load recomputes and rewrites the file automatically.

### Technology profile normalization

The 11 free-text technology & infrastructure answers go through `agents/technology_normalizer.py` — an LLM call (`deepseek/deepseek-v4-flash` by default, routed through OpenRouter) that detects "no answer" phrasing and canonicalizes shorthand into real product names (e.g. "in tune" → "Microsoft Intune"). This started on OpenAI's `gpt-4.1-mini` as the one deliberate exception to defaulting to Claude for LLM calls in this codebase, but moved to `deepseek/*` because this OpenRouter account's allowed-providers setting currently permits only the `deepseek` provider (`openai/*`/`anthropic/*` model ids 404 outright regardless of key validity). The call uses OpenRouter's `json_object` mode (deepseek doesn't support strict `json_schema` yet) with the expected shape validated by hand after parsing, and the result is still validated through the `TechnologyProfile` Pydantic model; on any API failure it falls back to the same deterministic phrase matching used for `industry` (`text_normalize.py`), so a missing key or an outage degrades onboarding rather than blocking it.

Requires `OPENROUTER_API_KEY` in `backend/.env` (git-ignored, loaded automatically via `python-dotenv` at startup). Without it, normalization silently falls back to phrase matching only.

Every non-blank raw answer is also preserved as a `MemoryFact` (`source: "onboarding"`) alongside the normalized value, so a human can check the LLM's interpretation against what the client actually typed.

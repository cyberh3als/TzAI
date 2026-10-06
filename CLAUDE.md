# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

### Backend (FastAPI + Python)

```bash
cd Truzta\ Agent\ Layer\ V1/backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
# Runs on http://localhost:8000; docs at http://localhost:8000/docs
```

### Frontend (React + Vite)

```bash
cd Truzta\ Agent\ Layer\ V1/frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

### Tests

```bash
cd Truzta\ Agent\ Layer\ V1/backend
pytest tests/ -v
pytest tests/test_onboarding.py  # single test file
pytest tests/test_onboarding.py::test_client_memory  # single test
```

## Architecture Overview

**Truzta Agent Layer** is a React + FastAPI SMB-focused GRC platform focused on compliance gap assessment. The system onboards organizations, persists their compliance profile, deterministically selects applicable controls, and (in development) interviews them about those controls.

```
frontend/ (React + Vite)
  ├── src/
  │   ├── App.jsx              Onboarding form UI
  │   └── ...
  └── package.json

backend/ (FastAPI)
  ├── app/
  │   ├── main.py              API routes + app setup
  │   ├── models.py            Pydantic contracts (ClientMemory, OnboardingSubmission, etc.)
  │   ├── onboarding.py        Orchestrates onboarding: memory → control selection
  │   ├── memory.py            Client memory persistence (YAML) + control list caching (JSON)
  │   ├── control_catalog.py   SCF queries and deterministic control filtering
  │   ├── control_tagging.py   Computes `development` and `physical` applicability tags
  │   ├── text_normalize.py    Deterministic phrase matching for "no answer" + industry
  │   ├── agents/
  │   │   ├── technology_normalizer.py  LLM call to normalize 11 tech questions (OpenRouter)
  │   │   └── gap_assessment/          Gap assessment interview + evaluation agents
  │   ├── prompts/             Reserved for versioned, editable prompt templates
  │   └── config.py            Paths, constants
  ├── tests/
  │   ├── test_onboarding.py   End-to-end onboarding
  │   ├── test_client_memory.py YAML persistence
  │   └── test_gap_interview.py Gap assessment interview flow
  ├── requirements.txt         Production dependencies
  └── requirements-dev.txt     +pytest, +httpx for testing

data/
  ├── catalog/
  │   ├── scf_controls.json    SCF universe, tagged in place (834 controls across 7 frameworks)
  │   └── relationships.json   Future: control-to-requirement, control-to-evidence, etc.
  ├── client-memory/           One YAML + one controls.json per onboarded client
  ├── schemas/                 JSON Schema validators for catalog records
  └── Small SCF JSON Master/   Source data (read-only, do not edit)
```

## Key Modules and Concepts

### Client Onboarding (`onboarding.py` → `POST /api/clients`)

Turns a client submission into two durable artifacts:

1. **Client Memory** (`data/client-memory/{client_id}.yaml`): Durable org profile, compliance target, applicability answers, normalized technology profile, and fact audit trail.
2. **Applicable Control List** (`data/client-memory/{client_id}.controls.json`): Organization-specific SCF controls (computed once at onboarding).

**Process**:
- Validates frameworks against the catalog.
- Normalizes free text via deterministic matching + LLM call (`agents/technology_normalizer.py`).
- Builds ClientMemory record with MemoryFact audit trail.
- Deterministically filters controls (see "Control Selection" below).
- Persists both artifacts, returns both to frontend.

### Control Selection (`control_catalog.py`)

**Deterministic filtering** applied to the catalog:

1. Include all controls applicable to the client's selected frameworks.
2. Exclude based on applicability tags:
   - `development` — dropped if client doesn't build/maintain software (takes priority).
   - `physical` — dropped if client is "Fully remote".

Tags are computed once by `control_tagging.py` from stable SCF fields (domain, control ID) and cached on `scf_controls.json` with a `tagging_version` stamp. Bump `TAGGING_VERSION` to recompute + rewrite.

### Technology Profile Normalization (`agents/technology_normalizer.py`)

11 free-text technology/infrastructure answers are normalized via LLM call:
- Detects "no answer" phrasing (not sure, none, idk, etc.).
- Canonicalizes shorthand into real product names (e.g. "in tune" → "Microsoft Intune").
- Falls back to deterministic phrase matching on API failure (degradation, not blocking).

**Current**: Uses `deepseek/deepseek-v4-flash` via OpenRouter (provider lock-in; no `anthropic/*` or `openai/*` allowed in account settings).

**Environment**: Requires `OPENROUTER_API_KEY` in `backend/.env` (git-ignored, auto-loaded via `python-dotenv`).

Every raw answer is preserved as a `MemoryFact` for human audit.

### Client Memory Persistence (YAML)

Why YAML (not directly a database):
- Human-readable diffs and corrections by developers.
- Validated through `ClientMemory` Pydantic model on load.
- Atomic writes, version number for future optimistic concurrency.

**Client YAML contains**:
- Durable facts (org profile, compliance target, applicability answers, normalized tech profile).
- NOT chat transcripts or hidden reasoning.
- Each learned fact records its source and confidence.

Generated client files are git-ignored; `example.yaml` documents the shape. For production, migrate to PostgreSQL for tenant isolation, concurrency, querying, encryption, and audit history. Only `yaml.safe_load` and `yaml.safe_dump` are used (no whitespace pitfalls).

### Deterministic Relationship Catalog (`data/catalog/relationships.json`)

Future source for explicit connections among controls, framework requirements, evidence types, and policies. Currently empty.

**Principle**: Relationships must not be invented. Each future record must include provenance and lifecycle status, validating against `data/schemas/relationship.schema.json`.

Agents should request changes through a deterministic service (not directly rewrite catalog files or decide mappings solely through prompts).

### Gap Assessment Agents (`agents/gap_assessment/`)

Interviewing, evaluation, follow-up, and synthetic answer generation for compliance gaps. **Not yet implemented**; contracts still under approval.

## API Endpoints

- `GET /api/health` — system health check.
- `GET /api/frameworks` — list frameworks in the catalog.
- `POST /api/clients` — run onboarding (validates, saves memory, computes applicable controls, returns both).
- `GET /api/clients` — list all onboarded clients (ClientSummary).
- `GET /api/clients/{client_id}` — get client memory (ClientMemory).
- `GET /api/clients/{client_id}/controls` — get cached applicable control list; computes once on first request if missing.

**Gap assessment endpoints are reserved but not yet implemented.**

## Important Design Decisions

### Determinism Over LLM

Onboarding is deterministic except for technology profile normalization. Control selection, tagging, and applicability filtering are rule-based, not LLM-driven. This ensures auditability and reproducibility.

### YAML for MVP, Database for Production

YAML enables rapid iteration and human validation. For production: migrate to PostgreSQL for transactions, encryption, audit history, and tenant isolation.

### OpenRouter Dependency

Technology normalization currently locks to `deepseek` via OpenRouter because the account's `allowed_providers` setting blocks `anthropic/*` and `openai/*` models outright (404). This is a known limitation; migration to Claude is higher-priority work.

### Tag Computation is Cached

Tags (`development`, `physical`) are computed once and cached on `scf_controls.json` with a `tagging_version` stamp. Never infer tags from free text at runtime. Bump `TAGGING_VERSION` in `control_tagging.py` when rules change; the next catalog load recomputes + rewrites automatically.

## Known Limitations

- **Assessment endpoints**: Not implemented; contracts still under approval.
- **OpenRouter lock-in**: `deepseek` is the only allowed provider. Migration to Claude planned.
- **YAML concurrency**: Not thread-safe. OK for MVP; production requires database.
- **Client memory file format**: Only YAML supported; JSON is computed once per client as a cache.

## Testing Patterns

Tests use `pytest` with fixtures for temporary client memory directories. See `tests/`:

- `test_onboarding.py`: End-to-end onboarding (submission → memory + controls).
- `test_client_memory.py`: YAML persistence and validation.
- `test_gap_interview.py`: Gap assessment interview flow.

Run all tests with `pytest tests/ -v` from `backend/`.

## Data Files and Ownership

- `data/catalog/` — Versioned shared GRC knowledge (SCF universe, future relationships). Do not silently modify; all changes must record provenance.
- `data/client-memory/` — One YAML + one controls.json per client. Generated during onboarding, git-ignored.
- `data/schemas/` — Machine-enforced contracts for catalog records (JSON Schema).
- `data/assessments/` — Reserved for assessment instances (not yet implemented).
- `Small SCF JSON Master/` — Source data (read-only). Do not edit directly; derived relationships must record provenance.

## Environment Variables

`backend/.env` (git-ignored, auto-loaded):
- `OPENROUTER_API_KEY` — Required for technology profile normalization. Without it, falls back to deterministic phrase matching.

## Common Tasks

### Add a new framework to the catalog

1. Place the SCF control data in `data/Small SCF JSON Master/`.
2. Update `control_catalog.py` to include it in the list.
3. Test onboarding with that framework selected.
4. Tag the controls if new applicability rules are needed (see "Control Selection").

### Change control applicability rules

1. Update the rule in `control_tagging.py` (e.g. the condition for `physical` tag).
2. Bump `TAGGING_VERSION`.
3. Next catalog load recomputes + rewrites `scf_controls.json` with new tags.

### Add a new onboarding question

1. Update `OnboardingSubmission` in `models.py` (add field).
2. Update the form in `frontend/src/App.jsx`.
3. Update `onboarding.py` if the answer drives control filtering or memory.
4. Test end-to-end via `POST /api/clients`.

### Migrate from OpenRouter to Claude for technology normalization

1. Replace `agents/technology_normalizer.py` to use `anthropic.Anthropic` (or Claude via the SDK).
2. Update `backend/requirements.txt` (add `anthropic`, remove `openrouter` if present).
3. Replace `OPENROUTER_API_KEY` env var with `ANTHROPIC_API_KEY`.
4. Test normalization with various tech product shorthand + "no answer" phrasing.

### Debug onboarding

1. Add print statements or a debugger (VS Code: `F5` in `backend/` with `.vscode/launch.json` configured).
2. Test against a minimal `OnboardingSubmission` (use `tests/test_onboarding.py` as a template).
3. Check `data/client-memory/{client_id}.yaml` for the persisted result.
4. Verify tags on affected controls in `data/catalog/scf_controls.json` (search for `"tags"`).

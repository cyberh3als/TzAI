# Gap question design — 70/30 mix and length control

Status: **planned, not implemented.** Only `backend/app/prompts/gap_assessment/question_generation.md`
and a small amount of budget logic in `questions.py` change. No data model or API change.

## The problem, measured

The current prompt asks for one binary ("Do you have…") question per control. Binary questions are
narrow, so they resist clustering and the questionnaire tracks control count almost 1:1:

| Client | Controls | Questions | Ratio |
|---|---|---|---|
| Review Checkpoint Co (ISO 27001) | 50 | 56 | 1.12 |
| Client with persistent controls (SOC 2) | 94 | ~106 projected | 1.12 |

ISO/HIPAA/GDPR sit at 40–55 controls, so ~60 questions is tolerable. SOC 2 at 94 controls projects to
**~106 questions**, which defeats the point of the product feeling simple.

## The mechanic: open-ended questions as the clustering lever

Binary questions can only ever be 1:1 — that is what makes them easy to answer, and also what makes
them long. Open-ended process questions are the opposite: one "walk me through how a change gets from
request to production" can legitimately cover 4–5 controls at once and yields richer evidence.

So the 70/30 split is not just a tone preference — **the 30% open-ended questions are the compression
mechanism.** Per domain:

- **~70% binary** — one per must-have artefact. These are the audit-evidence questions: does the
  policy/register/matrix exist, is it reviewed, is it signed.
- **~30% open-ended** — process questions that absorb the remaining controls in clusters. These carry
  multiple `control_ids` and are where the client explains themselves.

## Length control: a per-domain question budget

Ratio alone does not cap length. The prompt must receive an explicit target count per domain,
computed deterministically in Python and passed in the payload. Proposed sub-linear tiers:

| Controls in domain (N) | Target questions |
|---|---|
| 1–3 | N (no compression — too small to cluster) |
| 4–8 | ceil(0.75 × N) |
| 9–15 | ceil(0.55 × N) |
| 16+ | ceil(0.45 × N) |

## The catch: the long tail defeats this on its own

Measured domain distribution for the 94-control SOC 2 client — 23 domains, heavily long-tailed:

```
14  Identification & Authentication      3  Governance / Asset Mgmt / Config Mgmt
 9  Data Classification & Handling       2  x7 domains
 8  Human Resources Security             1  x3 domains
 7  Continuous Monitoring, Network Security
 5  Cryptographic Protections, Risk Mgmt, Third-Party Mgmt
 4  Information Assurance, Compliance
```

**13 of 23 domains have ≤3 controls.** Those 26 controls cannot compress within their own domain, so
per-domain budgeting alone only gets 94 controls → ~75 questions (+6 universal = 81). Better than 106,
still long.

Two ways to close the rest of the gap — **this is the main decision to make**:

- **Option A — cross-domain tail bucket.** Batch all ≤3-control domains into one LLM call and let it
  cluster across domain boundaries. Gets to ~69 total questions (ratio 0.73). Cost: some questions
  span unrelated domains and read a little oddly; the `domain` field becomes ambiguous for those.
- **Option B — leave the tail 1:1.** Accept ~81 questions for SOC 2. Every question stays cleanly
  inside one domain. Simpler, no architecture change.

Recommendation: **Option A**, with the tail bucket restricted to domains that are already thematically
adjacent, and `domain` set to a grouped label rather than null.

## Must-have artefact registry (your per-domain curation)

You mentioned wanting to go through the domains and name the must-have artefacts. That should be
**deterministic config, not prompt text** — consistent with how `universal_questions.py` and the
control tagging already work:

```
backend/app/agents/gap_assessment/domain_artifacts.py
    DOMAIN_ARTIFACTS = {
      "Third-Party Management": [
        "vendor security checklist used before onboarding",
        "register of third-party contracts and the systems each vendor can access",
        "third-party risk assessment performed before granting data access",
      ],
      ...
    }
```

Injected into the per-domain payload. The prompt is told: *every artefact listed for this domain must
have its own binary question; spend the remaining budget on open-ended process questions covering the
leftover controls.* This makes the 70% half human-controlled and auditable, and lets the LLM handle
only the clustering — which is the split the repo already uses everywhere else.

This registry can be filled in incrementally: domains without an entry fall back to today's behaviour.

## What stays deterministic

Unchanged — the prompt never owns these:

- Coverage guarantee: `_ensure_coverage()` still appends a 1:1 question for any dropped control.
- The per-domain budget is computed in Python and only *advisory* to the model; coverage wins over
  budget if they conflict.
- `_log_coverage_ratio()` should move from a global 0.7–1.0 band to a per-domain budget check.

## Known gap this does not fix

The LLM-failure fallback at `questions.py:98` emits the raw SCF `control_question` verbatim — jargon
heavy, often open-ended, and it ignores both the phrasing rules and the budget. It did not fire in
testing, but it is a hole in the guarantee. Fix separately: fall back to a templated
"Do you have <control name> in place?" instead of raw catalog text.

## Not changing

- Universal questions stay as they are, including the open-ended third-party vendor question —
  confirmed as intentional.
- `GapQuestion` / `GapAnswer` / `GapFinding` models, persistence, and the API contract are untouched.

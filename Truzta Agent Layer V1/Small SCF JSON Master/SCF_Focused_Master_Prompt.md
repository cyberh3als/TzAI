# Prompt: Full SCF - Focused SCF Master: 1500 controls to 300 controls spanning 10+ frameworks

You are given the **full Secure Controls Framework (SCF) 2026.2 JSON as input.**

Your task is to create a **new, smaller SCF JSON file** for use by the Gap Assessment Agent.

The goal of this step is **not** to perform organization-specific applicability filtering, redundancy reduction, SMB filtering, or final assessment scoping.

This step creates the **approved framework control universe** that later filtering stages will operate on.

## 1. Selected Frameworks

Only retain framework mappings for the following frameworks:

1. ISO 27001:2022
2. SOC 2
3. HIPAA Administrative
4. GDPR
5. Singapore PDPA
6. Malaysia PDPA
7. PCI DSS 4.0.1

Use the corresponding mappings from the full SCF JSON.

Where relevant, normalize the framework names in the output to:

- `ISO 27001`
- `SOC 2`
- `HIPAA Administrative`
- `GDPR`
- `Singapore PDPA`
- `Malaysia PDPA`
- `PCI DSS 4.0.1`

## 2. Selected SCF CORE Profiles

Retain the following SCF CORE applicability fields:

- SCF CORE Fundamentals
- SCF CORE ESP Level 1 Foundational
- SCF CORE ESP Level 2 Critical Infrastructure
- SCF CORE ESP Level 3 Advanced Threats
- SCF CORE AI Model Deployment
- SCF CORE AI-Enabled Operations

These SCF CORE fields are primarily retained for the separate workflow where an organization does not yet know which compliance framework it wants to pursue.

## 2.1 Keep columns possible solutions and considerations and ERL

Retain the following fields

- Possible Solutions & Considerations
   Micro-Small Business (<10 staff)
- Possible Solutions & Considerations
   Small Business (10-49 staff)
- Possible Solutions & Considerations
   Medium Business (50-249 staff)
- Possible Solutions & Considerations
   Large Business (250-999 staff)
- Possible Solutions & Considerations
   Enterprise (> 1,000 staff)
- Evidence Request List (ERL) #

These fields are retained to inform the gap assessment agent that will come later. You consider thee considerations when asked questions about how to implement controls for the client’s organsiation.

## 3. Framework Weight Gate

Before adding a framework mapping to the reduced JSON, apply the following **framework-specific minimum SCF control weight rules**.

### ISO 27001

Retain the control for ISO 27001 only when:

`weight >= 5`

### SOC 2

Retain the control for SOC 2 only when:

`weight == 10`

### HIPAA Administrative

Retain the control for HIPAA Administrative only when:

`weight == 10`

### GDPR

Retain the control for GDPR only when:

`weight >= 5`

### Singapore PDPA

Retain the control for Singapore PDPA only when:

`weight >= 5`

### Malaysia PDPA

Retain the control for Malaysia PDPA only when:

`weight >= 5`

### PCI DSS 4.0.1

Retain the control for PCI DSS 4.0.1 only when:

`weight >= 9`

## 4. Important Weight-Gate Behaviour

The weight gate must be applied **per framework**, not globally per SCF control.

A single SCF control may therefore remain applicable to one framework while being removed from another.

Example:

If an SCF control has:

`weight = 7`

and maps to:

- ISO 27001
- SOC 2
- GDPR

then the reduced result must be:

- ISO 27001 → retained
- SOC 2 → removed because SOC 2 requires weight 10
- GDPR → retained

Do not remove the entire SCF control merely because it fails the threshold for one framework.

## 5. Row Retention Rule

After applying the framework-specific weight gates, retain an SCF control in the smaller JSON when **either** of the following is true:

1. The control remains mapped to at least one selected framework after the framework weight gate has been applied; OR
2. The control belongs to at least one of the selected SCF CORE profiles.

If neither condition is true, remove the control entirely from the reduced JSON.

## 6. Fields to Retain for Every SCF Control

For each retained SCF control, keep only the following information:

### Core control information

- SCF Control ID / SCF #
- SCF Domain Number
- SCF Domain
- SCF Control Name
- SCF Control Description
- SCF Control Question
- SCF Control Weight
- Evidence Request List (ERL) #
- Conformity / Assessment Cadence, if available

### Business-size considerations

Retain:

- Possible Solutions & Considerations
   Micro-Small Business (<10 staff)
- Possible Solutions & Considerations
   Small Business (10-49 staff)
- Possible Solutions & Considerations
   Medium Business (50-249 staff)
- Possible Solutions & Considerations
   Large Business (250-999 staff)
- Possible Solutions & Considerations
   Enterprise (> 1,000 staff)

Preserve the original SCF text.

### SCR-CMM maturity criteria

Retain all available maturity criteria:

- Level 0
- Level 1
- Level 2
- Level 3
- Level 4
- Level 5

Preserve the original SCF text.

### SCF CORE applicability

Retain the selected SCF CORE fields listed in Section 2 as Boolean values.

### Framework applicability and mappings

For every selected framework, store:

- `applicable`
- `mapping`

However, `applicable` must reflect the result **after the framework-specific weight gate**.

If a framework fails the weight gate:

- set `applicable` to `false`
- set `mapping` to an empty string

Do not retain a framework mapping that has failed its weight threshold.

## 7. Derived Fields

For each retained SCF control, calculate:

### `selected_framework_count`

Number of selected frameworks for which the control remains `applicable: true` **after the framework weight gate**.

### `scf_core_profile_count`

Number of selected SCF CORE profiles where the control is marked `true`.

Do not create any calculated relative weighting or composite importance score.

The original SCF `weight` field must be retained unchanged.

## 8. Metadata

At the beginning of the output JSON, create a metadata section containing at minimum:

- Source: Secure Controls Framework (SCF)
- Source version
- Original SCF control count
- Reduced control count
- Selected frameworks
- Selected SCF CORE profiles
- Framework mapping keys used
- Framework weight gates used
- Selection rule

The selection rule should state substantially:

> Include a control if, after applying the framework-specific weight gates, it maps to at least one selected framework OR belongs to at least one selected SCF CORE profile.

Include the following machine-readable weight-gate configuration:

```
"framework_weight_gates": {
  "ISO 27001": {
    "operator": ">=",
    "weight": 5
  },
  "SOC 2": {
    "operator": "==",
    "weight": 10
  },
  "HIPAA Administrative": {
    "operator": "==",
    "weight": 10
  },
  "GDPR": {
    "operator": ">=",
    "weight": 5
  },
  "Singapore PDPA": {
    "operator": ">=",
    "weight": 5
  },
  "Malaysia PDPA": {
    "operator": ">=",
    "weight": 5
  },
  "PCI DSS 4.0.1": {
    "operator": ">=",
    "weight": 9
  }
}

```

## 9. Fields to Exclude

Do not include unrelated SCF fields.

Specifically exclude:

- NIST CSF Function Grouping
- PPTDF Applicability
- Any calculated relative weighting field
- Any calculated composite control importance score
- Frameworks outside the selected framework list
- SCF CORE profiles outside the selected profile list
- Other source columns that are not explicitly required above

Do not perform any relative-weight calculation.

The only weight used at this stage is the **original SCF control weight**, which is used to apply the framework weight gate.

## 10. Do Not Perform Later-Stage Filtering

Do **not** perform any of the following in this transformation:

- Redundancy filtering
- Semantic deduplication
- Consolidation of similar controls
- SMB applicability removal
- Organization-specific applicability filtering
- Technology-stack filtering
- Industry filtering
- Scope filtering
- Cloud/on-premises filtering
- Software-development filtering
- Privacy-data filtering
- Evidence filtering
- Audit readiness scoring

Those will be separate deterministic processing stages.

This prompt is only responsible for creating the **smaller framework-and-weight-filtered SCF universe**.

## 11. Output

Produce a valid JSON file containing:

1. `metadata`
2. `controls`

Do not modify the wording of SCF source content unless required to normalize field names.

Do not invent missing mappings or maturity criteria.

If a source field is missing, preserve it as an empty value or null rather than inferring content.

The resulting JSON should be significantly smaller than the full SCF JSON and should contain only:

- the required SCF control information,
- the selected framework mappings that survived their framework weight gates,
- selected SCF CORE profiles,
- business considerations,
- SCR-CMM maturity levels,
- and the specified derived counts.

#### **IMPORTANT for the Output:**

Organize the final JSON by framework rather than by unique SCF control. Create one top-level entry under `frameworks` for each selected framework. Each framework must contain its own `controls` array containing only the SCF controls that survived that framework's weight gate. If the same SCF control applies to multiple frameworks, duplicate that control into each applicable framework array. In each copy, `framework` and `framework_mapping` must refer only to that specific framework.

The output should look like:

```
{
  "metadata": {
    "source": "Secure Controls Framework (SCF)",
    "source_version": "2026.2",
    "source_reduced_universe_control_count": 834,

    "organization": "Controls are separated by framework after the framework-specific SCF weight gates.",

    "duplication_rule": "An SCF control may appear in more than one framework array when applicable to multiple frameworks.",

    "selected_frameworks": [
      "ISO 27001",
      "SOC 2",
      "HIPAA Administrative",
      "GDPR",
      "Singapore PDPA",
      "Malaysia PDPA",
      "PCI DSS 4.0.1"
    ],

    "framework_control_counts": {
      "ISO 27001": 50,
      "SOC 2": 100,
      "HIPAA Administrative": 57,
      "GDPR": 38,
      "Singapore PDPA": 28,
      "Malaysia PDPA": 17,
      "PCI DSS 4.0.1": 220
    }
  },

  "frameworks": {
    "<FRAMEWORK_NAME>": {
      "framework_name": "<normalized framework name>",
      "source_mapping_key": "<exact SCF source mapping key>",

      "weight_gate": {
        "operator": ">=",
        "weight": 5
      },

      "control_count": 0,

      "controls": [
        {
          "scf_id": "",
          "scf_domain_number": "",
          "scf_domain": "",
          "scf_control_name": "",
          "description": "",
          "control_question": "",
          "weight": "",
          "evidence_request_list_erl": null,
          "conformity_cadence": null,

          "business_size_considerations": {
            "micro_small_business_considerations": null,
            "small_business_considerations": null,
            "medium_business_considerations": null,
            "large_business_considerations": null,
            "enterprise_business_considerations": null
          },

          "scr_cmm": {
            "level_0": null,
            "level_1": null,
            "level_2": null,
            "level_3": null,
            "level_4": null,
            "level_5": null
          },

          "scf_core": {
            "SCF CORE Fundamentals": false,
            "SCF CORE ESP Level 1 Foundational": false,
            "SCF CORE ESP Level 2 Critical Infrastructure": false,
            "SCF CORE ESP Level 3 Advanced Threats": false,
            "SCF CORE AI Model Deployment": false,
            "SCF CORE AI-Enabled Operations": false
          },

          "framework": "<FRAMEWORK_NAME>",
          "framework_mapping": ""
        }
      ]
    }
  }
}

```

## 12. Appendix: Adding a New Framework Later

The reduced-universe creation process must support adding a **new framework that is not already listed above**.

Examples include:

- EU AI Act
- NIST CSF
- NIST 800-53
- DORA
- NIS2
- CCPA / CPRA
- ISO 42001
- another regulatory, privacy, cybersecurity, or AI governance framework contained in the full SCF JSON

When the user requests a new framework, do **not** immediately choose a weight threshold.

Instead, perform the following procedure.

### Step 1 — Locate the framework in the full SCF JSON

Inspect the full SCF JSON and identify the exact SCF framework mapping key corresponding to the framework requested by the user.

Do not infer or invent a mapping key.

If the requested framework is not present in the full JSON, inform the user that it cannot be added using this procedure without an additional mapping source.

### Step 2 — Count all SCF controls mapped to the new framework

Before proposing a weight gate, calculate the total number of SCF controls where the requested framework has a valid mapping.

Report this number to the user.

### Step 3 — Calculate the weight distribution

For the requested framework, calculate and present the following counts:

- Total mapped controls
- Weight = 10
- Weight >= 9
- Weight >= 8
- Weight >= 7
- Weight >= 6
- Weight >= 5

Present the results in a simple table.

Example structure:

| Threshold Number of mapped SCF controls  |   |
| ---------------------------------------- | - |
| All mapped controls                      | X |
| Weight = 10                              | X |
| Weight >= 9                              | X |
| Weight >= 8                              | X |
| Weight >= 7                              | X |
| Weight >= 6                              | X |
| Weight >= 5                              | X |

These counts must be calculated from the full SCF JSON. Do not estimate them.

### Step 4 — Evaluate the nature of the framework

Before recommending a weight gate, consider the nature of the requested framework.

Assess factors such as:

- Whether it is a broad cybersecurity control framework
- Whether it is a management-system standard
- Whether it is primarily a privacy or legal-regulatory framework
- Whether it is highly technical
- Whether the SCF mapping produces a very large number of controls
- Whether lower-weight controls may represent unique legal or regulatory obligations
- Whether the framework naturally expects risk-based applicability decisions
- Whether the framework contains substantial duplication when translated through SCF

Use these characteristics to determine how aggressively the initial framework universe should be reduced.

### Step 5 — Recommend a Weight Gate

Based on the control counts and the nature of the framework, recommend a **framework-specific weight gate**.

The recommendation must include:

1. The proposed gate
2. The number of controls that would remain
3. A short explanation of why that threshold is appropriate
4. At least one alternative threshold where useful

Example:

> Recommended gate: `weight >= 8`
>
> This reduces the framework from 240 mapped SCF controls to 92 controls. Because this is a broad cybersecurity framework with significant SCF mapping overlap, a stronger initial weight gate is appropriate.
>
> A more conservative option would be `weight >= 7`, which retains 126 controls.

Do not automatically apply the recommendation.

### Step 6 — Ask the User to Select the Gate

Present the recommendation and the relevant counts to the user.

The user must decide which threshold to use.

Once the user chooses the threshold, add the framework and its selected gate to:

- `selected_frameworks`
- `selected_framework_mapping_keys`
- `framework_weight_gates`

### Step 7 — Apply the Same Per-Framework Logic

Once approved, apply the new framework's weight gate in exactly the same way as the existing frameworks.

The gate must operate **only on that framework's mapping**.

A control failing the new framework's gate must not be deleted globally if it:

- survives another selected framework's gate; or
- belongs to a selected SCF CORE profile.

### Step 8 — Preserve Regulatory Coverage for Later Review

The weight gate is only the **first reduction mechanism**.

Do not assume that every control below the selected threshold is permanently irrelevant.

For frameworks where lower-weight SCF controls may represent unique legal, regulatory, or framework requirements, those controls may later be restored during the **Framework Coverage Guardrail** stage.

Do not perform that restoration during this initial JSON transformation unless specifically instructed.

### Step 9 — Update Metadata

When a new framework is added, update the output metadata to include:

- New framework name
- Exact source SCF mapping key
- Total originally mapped SCF controls
- Selected weight gate
- Number of controls surviving the gate

For example:

```
"framework_weight_gates": {
  "EU AI Act": {
    "operator": ">=",
    "weight": 7,
    "original_mapped_control_count": 120,
    "post_gate_control_count": 74
  }
}

```

### Step 10 — Repeatability Requirement

This procedure must be repeatable for any additional framework contained in the SCF source.

The decision process is therefore:

**New Framework Requested→ Find Exact SCF Mapping→ Count Mapped Controls→ Calculate Weight Distribution→ Evaluate Framework Type→ Recommend Weight Gate→ Show Resulting Control Counts→ User Selects Gate→ Add Framework to Reduced Universe Configuration**

Never choose a new framework's weight gate silently.

Always show the user the actual control counts from the full SCF JSON before recommending the threshold.
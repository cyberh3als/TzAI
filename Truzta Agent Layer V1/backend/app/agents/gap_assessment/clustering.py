"""Smart clustering strategy for reducing 700+ questions to 100-160 compound questions.

Groups controls hierarchically by domain → functional area → semantic similarity,
then creates compound questions covering 5-10 related controls per question.
This reduces assessment time from 13-20 hours to 3-4 hours.
"""

import json
import logging
from collections import defaultdict
from typing import NamedTuple

from openai import OpenAIError

from ...models import ClientMemory
from .client import QUESTION_MODEL, get_client
from .models import GapQuestion

logger = logging.getLogger(__name__)

# Control grouping targets: aim for 5-10 controls per question on average
_TARGET_CONTROLS_PER_QUESTION = 7
_MIN_CONTROLS_PER_QUESTION = 3
_MAX_CONTROLS_PER_QUESTION = 12

# Cluster prompt: asks LLM to identify functional areas within a domain
_CLUSTER_IDENTIFICATION_PROMPT = """You are an expert compliance assistant. Analyze the following controls within a domain and group them into logical functional areas.

Each group should contain controls that address the same compliance objective or operational capability. For example:
- "Board & Leadership Oversight" → controls about board approval, strategy review, CISO role
- "Risk Assessment & Management" → controls about risk identification, assessment, monitoring
- "User Access Control" → controls about authentication, authorization, privilege management

Return a JSON object with this structure:
{
  "clusters": [
    {
      "name": "Cluster Name",
      "description": "Brief description of what this cluster covers",
      "control_ids": ["ID1", "ID2", "ID3"]
    }
  ]
}

Focus on semantic grouping that helps an assessor answer similar questions together."""


class ControlCluster(NamedTuple):
    """A group of related controls that will be answered as one question."""
    name: str
    description: str
    control_ids: list[str]


def _identify_clusters(domain: str, controls: list[dict]) -> list[ControlCluster]:
    """Use LLM to identify functional clusters within a domain's controls."""
    if len(controls) <= _MIN_CONTROLS_PER_QUESTION:
        # Domain is small enough to ask as one question
        control_ids = [control["scf_id"] for control in controls]
        return [ControlCluster(
            name=domain,
            description=f"All {domain} controls",
            control_ids=control_ids,
        )]

    payload = {
        "domain": domain,
        "control_count": len(controls),
        "controls": [
            {
                "scf_id": control["scf_id"],
                "scf_control_name": control.get("scf_control_name", ""),
                "description": control.get("description", "")[:200],  # truncate
            }
            for control in controls
        ],
    }

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=QUESTION_MODEL,
            max_tokens=8000,
            messages=[
                {"role": "system", "content": _CLUSTER_IDENTIFICATION_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        clusters = result.get("clusters", [])
        if not clusters:
            # Fallback: return single cluster
            raise ValueError("No clusters returned")

        return [
            ControlCluster(
                name=c.get("name", domain),
                description=c.get("description", ""),
                control_ids=c.get("control_ids", []),
            )
            for c in clusters
        ]
    except (OpenAIError, json.JSONDecodeError, ValueError, KeyError, TypeError) as error:
        logger.warning(
            "Cluster identification failed for domain %r; using 1 cluster per %d controls: %s",
            domain, _TARGET_CONTROLS_PER_QUESTION, error,
        )
        # Fallback: split domain into equally-sized clusters
        control_ids = [control["scf_id"] for control in controls]
        cluster_size = max(_MIN_CONTROLS_PER_QUESTION, len(controls) // 3)
        clusters = []
        for i in range(0, len(control_ids), cluster_size):
            batch = control_ids[i:i + cluster_size]
            clusters.append(ControlCluster(
                name=f"{domain} (Part {i // cluster_size + 1})",
                description=f"Controls {batch[0]} to {batch[-1]}",
                control_ids=batch,
            ))
        return clusters


def cluster_controls_by_domain(controls: list[dict]) -> dict[str, list[ControlCluster]]:
    """Group controls by domain, then identify clusters within each domain."""
    by_domain: dict[str, list[dict]] = defaultdict(list)
    for control in controls:
        domain = control.get("scf_domain", "Uncategorized")
        by_domain[domain].append(control)

    logger.info("Grouping %d controls across %d domains for smart clustering", len(controls), len(by_domain))

    domain_clusters: dict[str, list[ControlCluster]] = {}
    for domain, domain_controls in by_domain.items():
        clusters = _identify_clusters(domain, domain_controls)
        domain_clusters[domain] = clusters
        logger.info("  %s: %d controls → %d clusters", domain, len(domain_controls), len(clusters))

    return domain_clusters


def generate_smart_questions(
    memory: ClientMemory,
    controls: list[dict],
    domain_clusters: dict[str, list[ControlCluster]],
) -> list[GapQuestion]:
    """Generate compound questions from domain clusters.

    Each question covers one cluster (typically 5-10 controls).
    The question text is generated by asking the LLM to create a compound assessment
    that covers the entire cluster semantically.
    """
    from .prompts import QUESTION_GENERATION_PROMPT
    from .universal_questions import UNIVERSAL_QUESTIONS

    raw_questions = [
        {
            "text": item["text"],
            "control_ids": [],
            "domain": None,
            "is_universal": True,
        }
        for item in UNIVERSAL_QUESTIONS
    ]

    memory_context = _memory_context_for_clustering(memory)
    question_order = 1

    for domain, clusters in domain_clusters.items():
        for cluster in clusters:
            # Build payload for cluster-level question generation
            cluster_controls = [c for c in controls if c["scf_id"] in cluster.control_ids]
            payload = {
                "domain": domain,
                "cluster_name": cluster.name,
                "cluster_description": cluster.description,
                "controls": [
                    {
                        "scf_id": control["scf_id"],
                        "control_question": control.get("control_question", ""),
                        "description": control.get("description", ""),
                    }
                    for control in cluster_controls
                ],
                "client_memory": memory_context,
            }

            try:
                client = get_client()
                response = client.chat.completions.create(
                    model=QUESTION_MODEL,
                    max_tokens=4000,
                    messages=[
                        {
                            "role": "system",
                            "content": _COMPOUND_QUESTION_GENERATION_PROMPT,
                        },
                        {"role": "user", "content": json.dumps(payload)},
                    ],
                    response_format={"type": "json_object"},
                )
                result = json.loads(response.choices[0].message.content)
                question_text = result.get("question", "")
                if not question_text:
                    raise ValueError("No question text returned")

                raw_questions.append({
                    "text": question_text,
                    "control_ids": cluster.control_ids,
                    "domain": domain,
                    "is_universal": False,
                })
                question_order += 1

            except (OpenAIError, json.JSONDecodeError, ValueError, KeyError, TypeError) as error:
                logger.warning(
                    "Failed to generate question for cluster %r in domain %r; using fallback: %s",
                    cluster.name, domain, error,
                )
                # Fallback: ask about the cluster by name
                fallback_text = (
                    f"Regarding {cluster.description.lower() if cluster.description else domain}, "
                    f"please describe your organization's implementation and controls."
                )
                raw_questions.append({
                    "text": fallback_text,
                    "control_ids": cluster.control_ids,
                    "domain": domain,
                    "is_universal": False,
                })
                question_order += 1

    # Ensure coverage: add 1:1 fallback for any missing controls
    covered = {control_id for item in raw_questions for control_id in item["control_ids"]}
    for control in controls:
        control_id = control["scf_id"]
        if control_id not in covered:
            raw_questions.append({
                "text": f"Do you have {control.get('scf_control_name', control_id)} in place?",
                "control_ids": [control_id],
                "domain": control.get("scf_domain"),
                "is_universal": False,
            })

    # Convert to GapQuestion objects
    return [
        GapQuestion(question_id=f"gq-{index:04d}", order=index, **item)
        for index, item in enumerate(raw_questions)
    ]


def _memory_context_for_clustering(memory: ClientMemory) -> dict:
    """Return a minimal memory context for LLM clustering."""
    return {
        "organization_name": memory.organization.name,
        "organization_size": memory.organization.size,
        "work_model": memory.applicability.work_model,
        "does_development": memory.applicability.does_development,
    }


_COMPOUND_QUESTION_GENERATION_PROMPT = """You are an expert compliance assessor designing compound assessment questions.

Your task: Create ONE assessment question that covers all controls in the cluster provided.
The question should:
1. Be phrased naturally (not a list of controls)
2. Ask about the organization's implementation and monitoring of these related capabilities
3. Be answerable by someone familiar with the organization's security program
4. Take 3-5 minutes to answer thoroughly
5. Use plain language, avoiding jargon where possible

Example:
Controls: "Multi-factor authentication", "Password policy", "Account lockout"
Cluster: "User Authentication"
Question: "Describe how your organization authenticates users, including the use of multi-factor authentication, password requirements, and account lockout mechanisms. What tools or services do you use?"

Return ONLY valid JSON with this structure:
{
  "question": "Your assessment question here"
}

Focus on creating a natural, conversational question that assesses all controls together."""

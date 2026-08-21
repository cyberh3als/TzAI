"""Deterministic applicability tags for SCF controls.

Tags mark a control as conditionally relevant, not framework-mapped. They are
computed once from stable SCF fields (domain, control ID) and cached on the
catalog file itself, so the same rules always produce the same tags. Nothing
here calls a model or infers meaning from free text at runtime.

- "development": relevant only to organisations that build or maintain
  software. Whole "Technology Development & Acquisition" domain, minus the
  handful of controls in that domain that apply to any technology consumer
  regardless of whether they write code (COTS purchasing, unsupported-asset
  management), plus the development-specific controls inside
  "Secure Engineering & Architecture" (the rest of that domain is general
  infrastructure architecture and applies either way).
- "physical": relevant only to organisations with a physical premises.
  Whole "Physical & Environmental Security" domain, plus the small set of
  Asset Management controls that are about physical equipment handling
  rather than logical asset tracking.

Bump TAGGING_VERSION whenever these rules change; ensure_tagged() then
recomputes and rewrites the cached file automatically.
"""

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

TAGGING_VERSION = 1

DEVELOPMENT_DOMAIN = "Technology Development & Acquisition"
DEVELOPMENT_DOMAIN_EXCLUDE_IDS = {
    "TDA-03",   # Commercial Off-The-Shelf (COTS) Security Solutions — applies to any software consumer
    "TDA-17",   # Unsupported Technology Assets, Applications and/or Services — applies to any technology asset
    "TDA-17.1",
}
DEVELOPMENT_EXTRA_IDS = {
    "SEA-01", "SEA-01.1",  # Secure engineering principles / centralized control management
    "SEA-02", "SEA-02.1", "SEA-02.3",  # Architecture alignment, terminology, technical debt
    "SEA-03",   # Defense-in-depth architecture
    "SEA-21",   # Application container
}

PHYSICAL_DOMAIN = "Physical & Environmental Security"
PHYSICAL_EXTRA_IDS = {
    "AST-05",   # Security of Assets & Media
    "AST-06",   # Unattended End-User Equipment
    "AST-08",   # Physical Tampering Detection
    "AST-09",   # Secure Disposal, Destruction or Re-Use of Equipment
}


def compute_tags(control: dict) -> list[str]:
    tags = []
    domain = control.get("scf_domain")
    scf_id = control.get("scf_id")

    is_development = (
        (domain == DEVELOPMENT_DOMAIN and scf_id not in DEVELOPMENT_DOMAIN_EXCLUDE_IDS)
        or scf_id in DEVELOPMENT_EXTRA_IDS
    )
    if is_development:
        tags.append("development")

    is_physical = domain == PHYSICAL_DOMAIN or scf_id in PHYSICAL_EXTRA_IDS
    if is_physical:
        tags.append("physical")

    return tags


def ensure_tagged(catalog: dict, path: Path) -> dict:
    """Tag every control if the cached file predates the current rules, else no-op."""
    metadata = catalog.setdefault("metadata", {})
    if metadata.get("tagging_version") == TAGGING_VERSION:
        return catalog

    for control in catalog["controls"]:
        control["tags"] = compute_tags(control)
    metadata["tagging_version"] = TAGGING_VERSION

    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as stream:
        json.dump(catalog, stream, indent=2, ensure_ascii=False)
        temporary = Path(stream.name)
    temporary.replace(path)

    return catalog

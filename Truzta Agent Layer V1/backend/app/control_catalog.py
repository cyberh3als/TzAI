"""Read-only queries and deterministic selection over the approved SCF catalog."""

import json
from pathlib import Path

from .control_tagging import ensure_tagged

WorkModel = str  # "Fully on-site" | "Fully remote" | "Hybrid"


def load_catalog(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        catalog = json.load(stream)
    return ensure_tagged(catalog, path)


def list_frameworks(catalog: dict) -> list[dict]:
    metadata = catalog["metadata"]
    counts = metadata["framework_control_counts"]
    return [
        {"name": name, "control_count": counts[name]["post_gate_control_count"]}
        for name in metadata["selected_frameworks"]
    ]


def validate_frameworks(catalog: dict, selected: list[str]) -> None:
    allowed = set(catalog["metadata"]["selected_frameworks"])
    unknown = set(selected) - allowed
    if unknown:
        raise ValueError(f"Unknown frameworks: {', '.join(sorted(unknown))}")


def select_controls(
    catalog: dict,
    frameworks: list[str],
    does_development: bool,
    work_model: WorkModel,
) -> list[dict]:
    """Return the controls applicable to a client's selected frameworks and profile.

    A control is included when it is applicable to at least one selected
    framework, then excluded if it carries a tag whose condition the client
    fails. "development" takes priority: a development-tagged control is
    dropped whenever the client does not do development, regardless of any
    other tag it also carries.
    """
    selected = []
    for control in catalog["controls"]:
        matched_frameworks = [
            framework
            for framework in frameworks
            if control["frameworks"].get(framework, {}).get("applicable")
        ]
        if not matched_frameworks:
            continue

        tags = control.get("tags", [])
        if "development" in tags and not does_development:
            continue
        if "physical" in tags and work_model == "Fully remote":
            continue

        selected.append({**control, "matched_frameworks": matched_frameworks})

    return selected

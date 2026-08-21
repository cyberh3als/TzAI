"""Deterministic finding priority, derived from SCF catalog fields — never from an LLM.

Why this isn't just `weight`
---------------------------
`weight` alone collapses for the frameworks that need prioritisation most. The
catalog's framework weight gates (see catalog metadata) admit SOC 2 and HIPAA
controls only at `weight == 10`, so every control in a SOC 2 client's set carries
the identical weight — measured: all 94 controls of the SOC 2 test client are
weight 10. Tiering on weight alone would label 100% of their findings "high".

So the score blends weight with two fields that do vary inside those sets:

    scf_core_profile_count    how many SCF CORE profiles include the control —
                              SCF's own signal of how foundational it is
    selected_framework_count  how many of the catalog's frameworks map to it —
                              breadth of obligation

Measured variance within that same all-weight-10 SOC 2 set: core-profile count
spans 0-5, framework count spans 1-6. Both discriminate where weight cannot.

Tiers are then cut by quantile *within the client's own control set* rather than
against fixed score thresholds, which guarantees a usable spread of high/medium/
low for any framework mix instead of bunching at one end.
"""

from typing import Literal

Priority = Literal["high", "medium", "low"]

# Weight dominates; the two count fields break ties and rescue the constant-weight
# frameworks. Doubling weight keeps it the primary signal where it does vary.
_WEIGHT_FACTOR = 2

# Share of the client's controls landing in each tier, highest score first.
_HIGH_SHARE = 0.25
_MEDIUM_SHARE = 0.45


def _as_int(value: object) -> int:
    """Catalog numerics arrive as strings (`"weight": "10"`); tolerate both."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def score_control(control: dict) -> int:
    return (
        _as_int(control.get("weight")) * _WEIGHT_FACTOR
        + _as_int(control.get("scf_core_profile_count"))
        + _as_int(control.get("selected_framework_count"))
    )


def build_priority_map(controls: list[dict]) -> dict[str, Priority]:
    """Map every control_id to a tier, cutting at quantiles of this client's own scores."""
    if not controls:
        return {}

    scored = sorted(
        ((control["scf_id"], score_control(control)) for control in controls),
        key=lambda pair: pair[1],
        reverse=True,
    )
    high_cut = max(1, round(len(scored) * _HIGH_SHARE))
    medium_cut = high_cut + max(1, round(len(scored) * _MEDIUM_SHARE))

    priorities: dict[str, Priority] = {}
    for index, (control_id, _) in enumerate(scored):
        if index < high_cut:
            priorities[control_id] = "high"
        elif index < medium_cut:
            priorities[control_id] = "medium"
        else:
            priorities[control_id] = "low"
    return priorities


def priority_for(control_ids: list[str], priority_map: dict[str, Priority]) -> Priority:
    """A finding inherits the highest priority among the controls it covers.

    Universal questions carry no control_ids; they get "medium" so they neither
    dominate nor disappear from a priority-sorted view.
    """
    tiers = [priority_map[cid] for cid in control_ids if cid in priority_map]
    if not tiers:
        return "medium"
    for tier in ("high", "medium", "low"):
        if tier in tiers:
            return tier  # type: ignore[return-value]
    return "low"

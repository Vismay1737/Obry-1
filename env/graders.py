"""
Deterministic graders for each task.
All scores are in [0.0, 1.0] with partial credit.
"""
from typing import Dict, Any


def grade_easy(state: Dict[str, Any]) -> float:
    """
    Easy task: Block at least 2 attacks.
    Partial scoring:
      - blocks_blocked / 2 capped at 1.0 = 70% weight
      - Low threat level bonus = 15% weight
      - No breach bonus = 15% weight
    """
    attacks_blocked = state.get("attacks_blocked", 0)
    breach_detected = state.get("breach_detected", False)
    threat_level = state.get("threat_level", 1.0)

    # Primary: blocking score (0 to 1 based on 2 required)
    block_score = min(1.0, attacks_blocked / 2.0)

    # Bonus: low threat
    threat_bonus = max(0.0, 1.0 - threat_level)

    # Bonus: no breach
    breach_bonus = 0.0 if breach_detected else 1.0

    score = (block_score * 0.70) + (threat_bonus * 0.15) + (breach_bonus * 0.15)
    return round(min(0.999, max(0.001, score)), 4)


def grade_medium(state: Dict[str, Any]) -> float:
    """
    Medium task: Block 4 attacks AND reduce open ports by 2.
    Partial scoring:
      - Block score (4 required) = 50% weight
      - Port reduction score (2 required) = 30% weight
      - Low threat bonus = 10% weight
      - No breach bonus = 10% weight
    """
    attacks_blocked = state.get("attacks_blocked", 0)
    breach_detected = state.get("breach_detected", False)
    threat_level = state.get("threat_level", 1.0)
    patches_applied = state.get("patches_applied", 0)

    # Primary: block score
    block_score = min(1.0, attacks_blocked / 4.0)

    # Secondary: port reduction score (proxy: patches applied)
    port_reduction_score = min(1.0, patches_applied / 2.0)

    # Bonus: low threat
    threat_bonus = max(0.0, 1.0 - threat_level)

    # Breach penalty
    breach_bonus = 0.0 if breach_detected else 1.0

    score = (
        (block_score * 0.50)
        + (port_reduction_score * 0.30)
        + (threat_bonus * 0.10)
        + (breach_bonus * 0.10)
    )
    return round(min(0.999, max(0.001, score)), 4)


def grade_hard(state: Dict[str, Any]) -> float:
    """
    Hard task: Block 6 attacks with zero breaches.
    Partial scoring:
      - Block score (6 required) = 60% weight
      - Zero breach bonus = 30% weight (single biggest factor)
      - Low threat bonus = 10% weight
    """
    attacks_blocked = state.get("attacks_blocked", 0)
    breach_detected = state.get("breach_detected", False)
    threat_level = state.get("threat_level", 1.0)
    missed_attacks = state.get("missed_attacks", 0)

    # Primary: block score
    block_score = min(1.0, attacks_blocked / 6.0)

    # Zero breach: binary but heavily weighted
    breach_bonus = 0.0 if breach_detected else 1.0

    # Threat bonus
    threat_bonus = max(0.0, 1.0 - threat_level)

    # Missed attack penalty modifier
    miss_penalty = min(0.3, missed_attacks * 0.05)

    score = (
        (block_score * 0.60)
        + (breach_bonus * 0.30)
        + (threat_bonus * 0.10)
        - miss_penalty
    )
    return round(min(0.999, max(0.001, score)), 4)


def grade(difficulty: str, state: Dict[str, Any]) -> float:
    """Route grading to the correct grader function."""
    graders = {
        "easy": grade_easy,
        "medium": grade_medium,
        "hard": grade_hard,
    }
    if difficulty not in graders:
        raise ValueError(f"Unknown difficulty: {difficulty}. Choose from {list(graders.keys())}")
    return graders[difficulty](state)

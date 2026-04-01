from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Task:
    task_id: str
    name: str
    description: str
    difficulty: str
    max_steps: int
    success_threshold: float
    metadata: Dict[str, Any] = field(default_factory=dict)


TASKS = {
    "easy": Task(
        task_id="cybersoc-easy",
        name="Basic Threat Response",
        description=(
            "Defend the SOC system by blocking at least 2 incoming attacks within 30 steps. "
            "The network starts with 3-5 open ports and moderate threat level. "
            "Success requires identifying and blocking active attack IPs."
        ),
        difficulty="easy",
        max_steps=30,
        success_threshold=0.5,
        metadata={
            "min_blocks_required": 2,
            "breach_penalty": False,
            "port_reduction_required": False,
        },
    ),
    "medium": Task(
        task_id="cybersoc-medium",
        name="Advanced Perimeter Defense",
        description=(
            "Block at least 4 attacks AND reduce open ports by at least 2 within 40 steps. "
            "The network starts with 5-7 open ports and elevated threat level. "
            "Requires both active threat neutralization and system hardening via patching."
        ),
        difficulty="medium",
        max_steps=40,
        success_threshold=0.6,
        metadata={
            "min_blocks_required": 4,
            "min_port_reduction": 2,
            "breach_penalty": True,
            "port_reduction_required": True,
        },
    ),
    "hard": Task(
        task_id="cybersoc-hard",
        name="Zero-Breach Incident Response",
        description=(
            "Block at least 6 attacks without allowing any system breach within 50 steps. "
            "The network starts with 7-10 open ports and high threat level. "
            "Any breach immediately ends the episode with heavy penalty. "
            "Requires strategic scanning, blocking, and patching in the correct order."
        ),
        difficulty="hard",
        max_steps=50,
        success_threshold=0.7,
        metadata={
            "min_blocks_required": 6,
            "breach_penalty": True,
            "breach_terminates": True,
            "port_reduction_required": False,
        },
    ),
}


def get_task(difficulty: str) -> Task:
    """Retrieve task configuration by difficulty level."""
    if difficulty not in TASKS:
        raise ValueError(f"Unknown difficulty '{difficulty}'. Choose from: {list(TASKS.keys())}")
    return TASKS[difficulty]


def list_tasks() -> Dict[str, Dict[str, Any]]:
    """Return a summary of all available tasks."""
    return {
        key: {
            "task_id": t.task_id,
            "name": t.name,
            "description": t.description,
            "difficulty": t.difficulty,
            "max_steps": t.max_steps,
            "success_threshold": t.success_threshold,
        }
        for key, t in TASKS.items()
    }

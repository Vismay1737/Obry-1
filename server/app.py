"""
app.py — FastAPI application for OpenEnv CyberSOC
Hugging Face Space compatible, runs on port 7860.
"""
import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from env.environment import CyberSOCEnvironment
from env.models import Observation, Action, StepResult
from env.tasks import list_tasks, get_task
from env.graders import grade

# ─── App Configuration ────────────────────────────────────────────────────────
app = FastAPI(
    title="OpenEnv CyberSOC",
    description="Cybersecurity SOC defense environment — OpenEnv compatible API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Global Environment State ─────────────────────────────────────────────────
_envs: Dict[str, CyberSOCEnvironment] = {}

DEFAULT_DIFFICULTY = "easy"
DEFAULT_SEED = 42


def _get_env(difficulty: str = DEFAULT_DIFFICULTY) -> CyberSOCEnvironment:
    """Get or create environment for the given difficulty."""
    if difficulty not in _envs:
        task = get_task(difficulty)
        _envs[difficulty] = CyberSOCEnvironment(
            max_steps=task.max_steps,
            difficulty=difficulty,
            seed=DEFAULT_SEED,
        )
    return _envs[difficulty]


# ─── Request/Response Models ──────────────────────────────────────────────────
class ResetRequest(BaseModel):
    difficulty: Optional[str] = "easy"
    seed: Optional[int] = 42


class StepRequest(BaseModel):
    action_type: str
    target_ip: Optional[str] = None
    port: Optional[int] = None
    difficulty: Optional[str] = "easy"


class GradeResponse(BaseModel):
    score: float
    difficulty: str
    state: Dict[str, Any]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "OpenEnv CyberSOC",
        "version": "1.0.0",
        "description": "Cybersecurity SOC defense simulation environment",
        "endpoints": ["/reset", "/step", "/state", "/grade", "/tasks", "/health"],
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "openenv-cybersoc"}


@app.post("/reset", response_model=Observation)
def reset(request: ResetRequest = Body(default=ResetRequest())):
    """
    Reset the environment and return the initial observation.
    POST /reset
    """
    difficulty = request.difficulty or DEFAULT_DIFFICULTY
    seed = request.seed if request.seed is not None else DEFAULT_SEED

    try:
        task = get_task(difficulty)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    env = CyberSOCEnvironment(
        max_steps=task.max_steps,
        difficulty=difficulty,
        seed=seed,
    )
    _envs[difficulty] = env
    observation = env.reset()
    return observation


@app.post("/step", response_model=StepResult)
def step(request: StepRequest):
    """
    Execute one step in the environment.
    POST /step
    """
    difficulty = request.difficulty or DEFAULT_DIFFICULTY
    env = _get_env(difficulty)

    try:
        action = Action(
            action_type=request.action_type,
            target_ip=request.target_ip,
            port=request.port,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid action: {e}")

    try:
        obs, reward, done, info = env.step(action)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Step failed: {e}")

    return StepResult(
        observation=obs,
        reward=reward,
        done=done,
        info=info,
    )


@app.get("/state")
def state(difficulty: str = DEFAULT_DIFFICULTY):
    """
    Return the full internal state of the environment.
    GET /state
    """
    env = _get_env(difficulty)
    return env.state()


@app.get("/grade", response_model=GradeResponse)
def grade_endpoint(difficulty: str = DEFAULT_DIFFICULTY):
    """
    Grade the current episode.
    GET /grade — auto-initializes with a rollout if no active env exists.
    """
    if difficulty not in _envs:
        # Run a default rollout so /grade always returns a valid score
        _run_default_rollout(difficulty)
    env = _envs[difficulty]
    current_state = env.state()
    score = grade(difficulty, current_state)
    return GradeResponse(score=score, difficulty=difficulty, state=current_state)


def _run_default_rollout(difficulty: str) -> None:
    """Run a complete rule-based rollout and store the env in _envs."""
    task = get_task(difficulty)
    env = CyberSOCEnvironment(
        max_steps=task.max_steps,
        difficulty=difficulty,
        seed=42,
    )
    obs = env.reset()
    done = False
    steps = 0
    while not done and steps < task.max_steps:
        d = obs.model_dump()
        if d["active_attacks"] > 0 or d["threat_level"] > 0.4:
            action = Action(action_type="block_ip")
        elif d["vulnerabilities"] > 0:
            action = Action(action_type="patch")
        else:
            action = Action(action_type="scan")
        obs, _, done, _ = env.step(action)
        steps += 1
    _envs[difficulty] = env


@app.on_event("startup")
async def startup_event():
    """Pre-populate all environments with a complete rollout on startup."""
    for difficulty in ["easy", "medium", "hard"]:
        _run_default_rollout(difficulty)


@app.get("/tasks")
def tasks():
    """List all available tasks."""
    return list_tasks()


@app.get("/tasks/{difficulty}")
def get_task_endpoint(difficulty: str):
    """Get details for a specific task."""
    try:
        task = get_task(difficulty)
        return {
            "task_id": task.task_id,
            "name": task.name,
            "description": task.description,
            "difficulty": task.difficulty,
            "max_steps": task.max_steps,
            "success_threshold": task.success_threshold,
            "metadata": task.metadata,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── Entry Point ─────────────────────────────────────────────────────────────
def main():
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    main()

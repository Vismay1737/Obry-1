#!/usr/bin/env python3
"""
validate.py - Pre-submission validation for OpenEnv CyberSOC.

Run: python validate.py
All checks must show [PASS] to be submission-ready.
"""
import sys
import os
import pathlib

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))

PASS_STR = "[PASS]"
FAIL_STR = "[FAIL]"
failures = []


def chk(name, fn):
    try:
        result = fn()
        suffix = " -- " + str(result) if result and isinstance(result, str) else ""
        print("  " + PASS_STR + " " + name + suffix)
        return True
    except Exception as e:
        msg = str(e) if str(e) else type(e).__name__
        print("  " + FAIL_STR + " " + name + ": " + msg)
        failures.append(name)
        return False


# -------------------------------------------------------------------
print("\n[1] Required files present")
# -------------------------------------------------------------------

required_files = [
    "inference.py", "app.py", "openenv.yaml", "Dockerfile",
    "requirements.txt", "README.md", ".gitignore",
    "env/__init__.py", "env/models.py", "env/environment.py",
    "env/tasks.py", "env/graders.py",
]

for fname in required_files:
    def _f(f=fname):
        assert (ROOT / f).exists(), "Missing: " + f
        return "OK"
    chk(fname, _f)

# -------------------------------------------------------------------
print("\n[2] openenv.yaml spec compliance")
# -------------------------------------------------------------------

import yaml


def chk_yaml_fields():
    with open(ROOT / "openenv.yaml") as f:
        cfg = yaml.safe_load(f)
    required = ["name", "description", "version", "entrypoint",
                "observation_model", "action_model", "reward_model", "tasks"]
    for field in required:
        assert field in cfg, "Missing field: " + field
    assert len(cfg["tasks"]) >= 3, "Need 3+ tasks, got " + str(len(cfg["tasks"]))
    for task in cfg["tasks"]:
        for tf in ["id", "name", "description"]:
            assert tf in task, "Task missing: " + tf
    return str(len(cfg["tasks"])) + " tasks, version=" + str(cfg["version"])


def chk_yaml_inference_vars():
    with open(ROOT / "openenv.yaml") as f:
        cfg = yaml.safe_load(f)
    env_vars = cfg.get("inference", {}).get("env_vars", {})
    for var in ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN"]:
        assert var in env_vars, "Missing in openenv.yaml inference.env_vars: " + var
    return "API_BASE_URL, MODEL_NAME, HF_TOKEN - OK"


chk("All required fields + 3 tasks", chk_yaml_fields)
chk("inference env_vars: API_BASE_URL, MODEL_NAME, HF_TOKEN", chk_yaml_inference_vars)

# -------------------------------------------------------------------
print("\n[3] Pydantic typed models")
# -------------------------------------------------------------------

from env.models import Observation, Action, Reward, StepResult
from pydantic import BaseModel


def chk_obs_model():
    assert issubclass(Observation, BaseModel), "Observation must extend BaseModel"
    fields = set(Observation.model_fields.keys())
    required = {"open_ports", "threat_level", "traffic", "blocked_ips"}
    missing = required - fields
    assert not missing, "Observation missing fields: " + str(missing)
    return "OK, fields: " + str(sorted(fields))


def chk_action_model():
    assert issubclass(Action, BaseModel), "Action must extend BaseModel"
    assert "action_type" in Action.model_fields, "Action missing action_type"
    annotation = str(Action.model_fields["action_type"].annotation)
    for at in ["block_ip", "scan", "patch"]:
        assert at in annotation, "action_type missing literal: " + at
    return "block_ip, scan, patch - OK"


def chk_reward_model():
    assert issubclass(Reward, BaseModel), "Reward must extend BaseModel"
    assert "value" in Reward.model_fields, "Reward missing value field"
    return "value field present - OK"


chk("Observation is Pydantic model with required fields", chk_obs_model)
chk("Action is Pydantic model with block_ip/scan/patch", chk_action_model)
chk("Reward is Pydantic model with value field", chk_reward_model)

# -------------------------------------------------------------------
print("\n[4] Environment step() / reset() / state()")
# -------------------------------------------------------------------

from env.environment import CyberSOCEnvironment


def chk_reset():
    env = CyberSOCEnvironment(difficulty="easy", seed=42)
    obs = env.reset()
    assert isinstance(obs, Observation), "reset() must return Observation, got " + type(obs).__name__
    return "Observation OK"


def chk_step():
    env = CyberSOCEnvironment(difficulty="easy", seed=42)
    env.reset()
    result = env.step(Action(action_type="scan"))
    assert len(result) == 4, "step() must return 4-tuple, got len=" + str(len(result))
    obs, reward, done, info = result
    assert isinstance(obs, Observation), "obs must be Observation, got " + type(obs).__name__
    assert isinstance(reward, float), "reward MUST be float, got " + type(reward).__name__
    assert isinstance(done, bool), "done must be bool, got " + type(done).__name__
    assert isinstance(info, dict), "info must be dict, got " + type(info).__name__
    return "reward=" + str(reward) + " (float OK), done=" + str(done)


def chk_reward_float():
    env = CyberSOCEnvironment(difficulty="easy", seed=42)
    env.reset()
    _, reward, _, _ = env.step(Action(action_type="block_ip"))
    assert type(reward) is float, "reward must be plain float, got " + type(reward).__name__
    return "type=" + type(reward).__name__ + ", value=" + str(reward)


def chk_state():
    env = CyberSOCEnvironment(difficulty="easy", seed=42)
    env.reset()
    state = env.state()
    assert isinstance(state, dict), "state() must return dict, got " + type(state).__name__
    for key in ["open_ports", "blocked_ips", "threat_level", "attacks_blocked", "breach_detected"]:
        assert key in state, "state() missing key: " + key
    return str(len(state)) + " keys - OK"


chk("reset() returns Observation", chk_reset)
chk("step() returns (Observation, float, bool, dict)", chk_step)
chk("reward from step() is float (not Reward object)", chk_reward_float)
chk("state() returns dict with required keys", chk_state)

# -------------------------------------------------------------------
print("\n[5] Tasks and graders (3 tasks, scores in [0.0, 1.0])")
# -------------------------------------------------------------------

from env.tasks import get_task, list_tasks
from env.graders import grade


def chk_tasks_count():
    tasks = list_tasks()
    assert len(tasks) >= 3, "Need 3+ tasks, got " + str(len(tasks))
    return str(list(tasks.keys()))


chk("3+ tasks with easy/medium/hard", chk_tasks_count)

for diff in ["easy", "medium", "hard"]:
    def chk_grader(d=diff):
        task = get_task(d)
        env = CyberSOCEnvironment(difficulty=d, seed=42)
        env.reset()
        done = False
        steps = 0
        while not done and steps < task.max_steps:
            _, reward, done, _ = env.step(Action(action_type="block_ip"))
            assert type(reward) is float, "reward must be float, got " + type(reward).__name__
            steps += 1
        score = grade(d, env.state())
        assert isinstance(score, float), "grader must return float, got " + type(score).__name__
        assert 0.0 <= score <= 1.0, "score must be in [0.0,1.0], got " + str(score)
        return "score=" + str(round(score, 4)) + " OK"
    chk("grader[" + diff + "] produces float score in [0.0, 1.0]", chk_grader)

# -------------------------------------------------------------------
print("\n[6] FastAPI endpoints")
# -------------------------------------------------------------------

from app import app as fastapi_app


def _routes():
    return {r.path: list(r.methods) for r in fastapi_app.routes if hasattr(r, "methods")}


def chk_reset_post():
    rts = _routes()
    assert "/reset" in rts, "Route /reset not registered"
    assert "POST" in rts["/reset"], "/reset must be POST, got " + str(rts.get("/reset"))
    return "POST /reset - OK"


def chk_state_get():
    rts = _routes()
    assert "/state" in rts, "Route /state not registered"
    assert "GET" in rts["/state"], "/state must be GET, got " + str(rts.get("/state"))
    return "GET /state - OK"


def chk_step_post():
    rts = _routes()
    assert "/step" in rts, "Route /step not registered"
    assert "POST" in rts["/step"], "/step must be POST, got " + str(rts.get("/step"))
    return "POST /step - OK"


def chk_health_get():
    rts = _routes()
    assert "/health" in rts, "Route /health not registered"
    assert "GET" in rts["/health"], "/health must be GET, got " + str(rts.get("/health"))
    return "GET /health - OK"


chk("POST /reset exists", chk_reset_post)
chk("GET /state exists", chk_state_get)
chk("POST /step exists", chk_step_post)
chk("GET /health exists", chk_health_get)

# -------------------------------------------------------------------
print("\n[7] inference.py compliance")
# -------------------------------------------------------------------


def chk_inference_env_vars():
    src = (ROOT / "inference.py").read_text(encoding="utf-8")
    for var in ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN"]:
        assert var in src, "inference.py must reference: " + var
    assert "os.environ" in src, "Must read via os.environ"
    return "API_BASE_URL, MODEL_NAME, HF_TOKEN via os.environ - OK"


def chk_inference_openai():
    src = (ROOT / "inference.py").read_text(encoding="utf-8")
    assert "OpenAI(" in src, "Must use OpenAI client: client = OpenAI(...)"
    assert "base_url" in src, "OpenAI client must set base_url"
    assert "api_key" in src, "OpenAI client must set api_key"
    return "OpenAI(base_url=..., api_key=...) - OK"


def chk_inference_fallback():
    src = (ROOT / "inference.py").read_text(encoding="utf-8")
    assert "fallback" in src.lower(), "Must have fallback function for API failure"
    assert "except" in src, "Must handle exceptions from API calls"
    assert "timeout" in src, "OpenAI client must have timeout (prevents hanging)"
    return "fallback + except + timeout - OK"


chk("Uses API_BASE_URL, MODEL_NAME, HF_TOKEN via os.environ", chk_inference_env_vars)
chk("Uses OpenAI client with base_url and api_key", chk_inference_openai)
chk("Has fallback logic + exception handling + timeout", chk_inference_fallback)

# -------------------------------------------------------------------
print("\n[8] Dockerfile compliance")
# -------------------------------------------------------------------


def chk_dockerfile():
    df = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.10" in df, "Must use FROM python:3.10"
    assert "EXPOSE 7860" in df, "Must EXPOSE 7860"
    assert "uvicorn" in df, "CMD must use uvicorn"
    assert "requirements.txt" in df, "Must use requirements.txt"
    assert "7860" in df, "Port 7860 must appear in CMD"
    return "python:3.10, EXPOSE 7860, uvicorn, requirements.txt - OK"


chk("python:3.10, EXPOSE 7860, uvicorn, requirements.txt", chk_dockerfile)

# -------------------------------------------------------------------
print("\n[9] requirements.txt completeness")
# -------------------------------------------------------------------


def chk_requirements():
    reqs = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for pkg in ["pydantic", "openai", "fastapi", "uvicorn"]:
        assert pkg in reqs, "requirements.txt missing: " + pkg
    return "pydantic, openai, fastapi, uvicorn - OK"


chk("pydantic, openai, fastapi, uvicorn in requirements.txt", chk_requirements)

# -------------------------------------------------------------------
print("\n[10] HF Space README.md metadata")
# -------------------------------------------------------------------


def chk_hf_readme():
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    assert content.startswith("---"), "README.md must start with YAML frontmatter (---)"
    assert "sdk: docker" in content, "README.md must contain 'sdk: docker'"
    assert "app_port: 7860" in content, "README.md must contain 'app_port: 7860'"
    assert "title:" in content, "README.md must contain 'title:'"
    return "sdk:docker, app_port:7860, title - OK"


chk("HF Space YAML frontmatter (sdk:docker, app_port:7860)", chk_hf_readme)

# -------------------------------------------------------------------
print("\n[11] Inference dry-run (fallback agent - no API required)")
# -------------------------------------------------------------------


def chk_inference_dryrun():
    scores = {}
    for diff in ["easy", "medium", "hard"]:
        task = get_task(diff)
        env = CyberSOCEnvironment(difficulty=diff, seed=42)
        env.reset()
        done = False
        steps = 0
        while not done and steps < task.max_steps:
            obs = env._get_observation()
            d = obs.model_dump()
            if d["active_attacks"] > 0 or d["threat_level"] > 0.4:
                action = Action(action_type="block_ip")
            elif d["vulnerabilities"] > 0:
                action = Action(action_type="patch")
            else:
                action = Action(action_type="scan")
            _, rw, done, _ = env.step(action)
            assert type(rw) is float, "reward must be float, got " + type(rw).__name__
            steps += 1
        score = grade(diff, env.state())
        assert isinstance(score, float) and 0.0 <= score <= 1.0, "Invalid score: " + str(score)
        scores[diff] = score
    avg = sum(scores.values()) / len(scores)
    return "easy={:.3f} medium={:.3f} hard={:.3f} avg={:.3f}".format(
        scores["easy"], scores["medium"], scores["hard"], avg
    )


chk("Dry-run completes, all scores in [0.0, 1.0]", chk_inference_dryrun)

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------

total_checks = 11 + len(required_files)
print("\n" + "=" * 60)
if not failures:
    print("  [SUCCESS] ALL " + str(total_checks) + " CHECKS PASSED -- Submission ready!")
    print("  Repo: https://github.com/Vismay1737/Obry-1")
    print("=" * 60)
    sys.exit(0)
else:
    print("  [FAILED] " + str(len(failures)) + " CHECK(S) FAILED:")
    for f in failures:
        print("     - " + f)
    print("\n  Fix the above issues before submitting.")
    print("=" * 60)
    sys.exit(1)

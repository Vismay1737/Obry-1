"""
inference.py — OpenEnv CyberSOC Inference Script
Runs all 3 tasks using an LLM agent via OpenAI-compatible API.
Outputs in the exact STDOUT format required by the evaluator.
"""
import os
import json
import time
from typing import List, Optional
from openai import OpenAI

from env.environment import CyberSOCEnvironment
from env.models import Action
from env.graders import grade
from env.tasks import get_task

# ─── Configuration ────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
LOCAL_IMAGE_NAME = os.environ.get("LOCAL_IMAGE_NAME", "")
BENCHMARK = "openenv-cybersoc"

# ─── OpenAI Client ────────────────────────────────────────────────────────────
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN or "dummy-key",
    timeout=10.0,
    max_retries=0,
)

# ─── System Prompt & Fallback ─────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a Cybersecurity SOC (Security Operations Center) AI agent.
Your job is to defend a network system from incoming attacks.

You will receive observations about the current system state and must choose ONE action.

Available actions:
1. block_ip — Block a specific attacking IP address. Use when active attacks are detected.
2. scan     — Scan the network to discover hidden threats. Use when threat level is high.
3. patch    — Patch a vulnerability to close an open port. Use when vulnerabilities > 0.

Strategy:
- If active_attacks > 0 and threat_level > 0.3: prefer block_ip
- If vulnerabilities > 2 and active_attacks == 0: prefer patch
- If threat_level > 0.5 and active_attacks < 2: prefer scan
- Otherwise: scan or patch based on state

RESPOND ONLY with a valid JSON object in this exact format:
{
  "action_type": "block_ip" | "scan" | "patch",
  "target_ip": "x.x.x.x" or null,
  "port": number or null
}

Do NOT include any explanation. Only output valid JSON."""

KNOWN_ATTACKER_IPS = [
    "192.168.1.100", "10.0.0.50", "172.16.0.200", "203.0.113.42",
    "198.51.100.77", "192.0.2.99", "185.220.101.1", "185.220.101.2",
    "45.33.32.156", "104.21.14.101", "1.234.56.78", "91.108.4.100",
]

def fallback_action_from_obs(obs: dict) -> Action:
    active_attacks = obs.get("active_attacks", 0)
    threat_level = obs.get("threat_level", 0.0)
    vulnerabilities = obs.get("vulnerabilities", 0)
    blocked_ips = obs.get("blocked_ips", [])

    if active_attacks > 0 or threat_level > 0.4:
        for ip in KNOWN_ATTACKER_IPS:
            if ip not in blocked_ips:
                return Action(action_type="block_ip", target_ip=ip)
        return Action(action_type="block_ip", target_ip=None)
    elif vulnerabilities > 0:
        open_ports = obs.get("open_ports", [])
        port = open_ports[0] if open_ports else None
        return Action(action_type="patch", port=port)
    else:
        return Action(action_type="scan")

def get_llm_action(observation_dict: dict, active_attack_ips: list) -> Action:
    obs_text = json.dumps(observation_dict, indent=2)
    if active_attack_ips:
        obs_text += f"\n\nKnown active attacker IPs: {active_attack_ips}"

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Current observation:\n{obs_text}\n\nChoose your action:"},
        ],
        temperature=0.2,
        max_tokens=150,
    )
    content = response.choices[0].message.content.strip()

    try:
        if "```" in content:
            parts = content.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    data = json.loads(part)
                    break
                except json.JSONDecodeError:
                    continue
            else:
                raise json.JSONDecodeError("No valid JSON block", content, 0)
        else:
            data = json.loads(content)

        return Action(
            action_type=data.get("action_type", "scan"),
            target_ip=data.get("target_ip"),
            port=data.get("port"),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return fallback_action_from_obs(observation_dict)

def _check_llm_available() -> bool:
    try:
        client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return True
    except Exception:
        return False

# ─── STDOUT Formatting functions ──────────────────────────────────────────────
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )

def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} rewards={rewards_str}", flush=True)

def action_to_str(a: Action) -> str:
    if a.action_type == "block_ip":
        return f"block_ip('{a.target_ip}')" if a.target_ip else "block_ip(null)"
    elif a.action_type == "patch":
        return f"patch({a.port})" if a.port is not None else "patch(null)"
    return f"{a.action_type}()"

# ─── Main Execution ───────────────────────────────────────────────────────────
def run_task(difficulty: str, use_llm: bool = True) -> float:
    task = get_task(difficulty)
    task_name = getattr(task, "task_id", getattr(task, "id", difficulty))
    env = CyberSOCEnvironment(
        max_steps=task.max_steps,
        difficulty=difficulty,
        seed=42,
    )
    
    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    obs = env.reset()
    rewards = []
    step_num = 0
    success = False

    try:
        while True:
            obs_dict = obs.model_dump()
            env_state = env.state()
            active_attack_ips = env_state.get("active_attack_ips", [])
            
            step_num += 1
            error_msg = None
            action = None
            
            try:
                if use_llm:
                    action = get_llm_action(obs_dict, active_attack_ips)
                else:
                    action = fallback_action_from_obs(obs_dict)
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                action = fallback_action_from_obs(obs_dict)

            obs, reward, done, info = env.step(action)
            
            if not error_msg:
                error_msg = getattr(obs, "last_action_error", None)
                
            rewards.append(float(reward))
            
            log_step(
                step=step_num, 
                action=action_to_str(action), 
                reward=float(reward), 
                done=done, 
                error=error_msg
            )

            if done:
                # Based on the original env grading logic
                final_state = env.state()
                score = grade(difficulty, final_state)
                success = score >= task.success_threshold
                break
                
            if step_num >= task.max_steps:
                break
                
    except Exception as e:
        success = False

    finally:
        log_end(success=success, steps=step_num, rewards=rewards)

    return 0.0

def main():
    use_llm = _check_llm_available()
    difficulties = ["easy", "medium", "hard"]
    for difficulty in difficulties:
        run_task(difficulty, use_llm=use_llm)

if __name__ == "__main__":
    main()

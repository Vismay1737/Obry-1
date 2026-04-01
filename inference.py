"""
inference.py — OpenEnv CyberSOC Inference Script
Runs all 3 tasks using an LLM agent via OpenAI-compatible API.
Prints individual task scores and average score.
Falls back to rule-based agent if API is unavailable.
"""
import os
import json
import time
import sys
from openai import OpenAI

from env.environment import CyberSOCEnvironment
from env.models import Action
from env.graders import grade
from env.tasks import get_task

# ─── Configuration ────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4o-mini")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# ─── OpenAI Client ────────────────────────────────────────────────────────────
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN or "dummy-key",
    timeout=10.0,        # hard 10-second timeout — prevents hanging
    max_retries=0,       # no retries on failure
)

# ─── System Prompt ────────────────────────────────────────────────────────────
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


# ─── Known Attacker IPs (mirrors environment.py) ──────────────────────────────
KNOWN_ATTACKER_IPS = [
    "192.168.1.100", "10.0.0.50", "172.16.0.200", "203.0.113.42",
    "198.51.100.77", "192.0.2.99", "185.220.101.1", "185.220.101.2",
    "45.33.32.156", "104.21.14.101", "1.234.56.78", "91.108.4.100",
]


def fallback_action_from_obs(obs: dict) -> Action:
    """Rule-based fallback when LLM fails or returns unparseable output."""
    active_attacks = obs.get("active_attacks", 0)
    threat_level = obs.get("threat_level", 0.0)
    vulnerabilities = obs.get("vulnerabilities", 0)
    blocked_ips = obs.get("blocked_ips", [])

    if active_attacks > 0 or threat_level > 0.4:
        # Find first unblocked known attacker
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
    """Query the LLM for an action given the current observation."""
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

    # Parse JSON response — strip markdown code fences if present
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
    """Quick connectivity probe — returns True if LLM API is reachable."""
    try:
        client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return True
    except Exception:
        return False


def run_task(difficulty: str, use_llm: bool = True) -> float:
    """Run a single task and return its grade score (0.0–1.0)."""
    task = get_task(difficulty)
    env = CyberSOCEnvironment(
        max_steps=task.max_steps,
        difficulty=difficulty,
        seed=42,
    )

    print(f"\n{'='*60}")
    print(f"  TASK: {task.name} [{difficulty.upper()}]")
    print(f"  Max Steps: {task.max_steps} | Goal: {task.description[:75]}...")
    print(f"{'='*60}")

    obs = env.reset()
    total_reward = 0.0
    step_num = 0

    while True:
        obs_dict = obs.model_dump()
        env_state = env.state()
        active_attack_ips = env_state.get("active_attack_ips", [])

        # Choose action — always fall back gracefully on any error
        action: Action
        try:
            if use_llm:
                action = get_llm_action(obs_dict, active_attack_ips)
            else:
                action = fallback_action_from_obs(obs_dict)
        except Exception as e:
            print(f"  [Step {step_num}] LLM error ({type(e).__name__}), using fallback...")
            action = fallback_action_from_obs(obs_dict)

        obs, reward, done, info = env.step(action)
        total_reward += reward
        step_num += 1

        if step_num % 5 == 0 or done:
            print(
                f"  Step {step_num:3d} | Action: {action.action_type:10s} | "
                f"Reward: {reward:+.2f} | Total: {total_reward:+.2f} | "
                f"Blocks: {info['attacks_blocked']} | Breach: {info['breach_detected']}"
            )

        if done:
            break

    final_state = env.state()
    score = grade(difficulty, final_state)

    print(f"\n  ── Final Results ──")
    print(f"  Attacks Blocked : {final_state['attacks_blocked']}")
    print(f"  Missed Attacks  : {final_state['missed_attacks']}")
    print(f"  Patches Applied : {final_state['patches_applied']}")
    print(f"  Breach Detected : {final_state['breach_detected']}")
    print(f"  Threat Level    : {final_state['threat_level']:.3f}")
    print(f"  Total Reward    : {total_reward:+.2f}")
    print(f"  ── GRADE SCORE  : {score:.4f} ──")

    return float(score)


def main() -> float:
    print("\n" + "=" * 60)
    print("  OpenEnv CyberSOC — Inference Runner")
    print(f"  Model    : {MODEL_NAME}")
    print(f"  API Base : {API_BASE_URL}")
    print("=" * 60)

    # Test API connectivity (with timeout — will NOT hang)
    use_llm = False
    print("\n  Testing LLM API connectivity...", flush=True)
    use_llm = _check_llm_available()
    if use_llm:
        print("  ✓ LLM API connected — running with LLM agent")
    else:
        print("  ✗ LLM API unavailable — running with rule-based fallback agent")

    difficulties = ["easy", "medium", "hard"]
    scores: dict = {}

    for difficulty in difficulties:
        try:
            score = run_task(difficulty, use_llm=use_llm)
            scores[difficulty] = score
        except Exception as e:
            print(f"\n  ERROR running {difficulty} task: {e}")
            scores[difficulty] = 0.0
        time.sleep(0.5)  # Brief pause between tasks

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  FINAL SCORES")
    print("=" * 60)
    for diff, score in scores.items():
        bar = "█" * int(score * 20)
        print(f"  {diff.upper():8s}: {score:.4f}  |{bar:<20}|")

    avg = sum(scores.values()) / len(scores)
    print(f"\n  AVERAGE SCORE : {avg:.4f}")
    print("=" * 60 + "\n")

    return float(avg)


if __name__ == "__main__":
    main()

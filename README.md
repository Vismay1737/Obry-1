---
title: OpenEnv CyberSOC
emoji: 🛡️
colorFrom: blue
colorTo: green
sdk: docker
tags:
  - openenv
app_port: 7860
pinned: false
license: mit
short_description: Cybersecurity SOC defense simulation - OpenEnv
---

# 🛡️ OpenEnv CyberSOC — Cybersecurity Defense Environment

A production-ready **OpenEnv**-compatible reinforcement learning environment that simulates a Cybersecurity Security Operations Center (SOC). An AI agent defends a network system from incoming attacks by blocking IPs, scanning for threats, and patching vulnerabilities.

---

## 📋 Table of Contents
- [Project Description](#project-description)
- [Action Space](#action-space)
- [Observation Space](#observation-space)
- [Reward Structure](#reward-structure)
- [Task Descriptions](#task-descriptions)
- [Grading](#grading)
- [Setup Instructions](#setup-instructions)
- [Running with Docker](#running-with-docker)
- [Running the FastAPI Server](#running-the-fastapi-server)
- [How to Run Inference](#how-to-run-inference)
- [API Reference](#api-reference)
- [Expected Baseline Scores](#expected-baseline-scores)
- [Project Structure](#project-structure)

---

## 🧠 Project Description

The **CyberSOC environment** models a real-world network defense scenario where an agent must:

1. **Detect** incoming attacks via scanning
2. **Block** malicious IP addresses before they breach the system
3. **Patch** open vulnerabilities to reduce the attack surface
4. **Avoid breaches** that result in heavy penalties

The environment supports three difficulty levels with increasing attack frequency and stricter success criteria. It is fully compatible with the **OpenEnv specification** and exposes a FastAPI HTTP interface for agent interaction.

---

## 🎮 Action Space

The agent has **3 available actions** per step:

| Action | Field | Description |
|--------|-------|-------------|
| `block_ip` | `target_ip` (optional str) | Block a specific attacking IP address. If `target_ip` is `null`, blocks the first active attacker automatically. |
| `scan` | — | Scan the network to discover hidden threats. Reveals new attack IPs and improves situational awareness. |
| `patch` | `port` (optional int) | Patch a system vulnerability. Closes an open port and reduces `vulnerabilities` count. |

### Action JSON Format
```json
{
  "action_type": "block_ip",
  "target_ip": "192.168.1.100",
  "port": null
}
```

---

## 👁️ Observation Space

Each step returns an `Observation` object with these fields:

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `open_ports` | `list[int]` | — | Currently open (vulnerable) ports on the system |
| `threat_level` | `float` | `[0.0, 1.0]` | Current threat level (0 = safe, 1 = critical) |
| `traffic` | `int` | `≥ 0` | Network traffic volume in requests/sec |
| `blocked_ips` | `list[str]` | — | IP addresses that have been blocked |
| `active_attacks` | `int` | `≥ 0` | Number of currently active incoming attacks |
| `vulnerabilities` | `int` | `≥ 0` | Number of unpatched system vulnerabilities |
| `breach_detected` | `bool` | — | Whether a system breach has occurred |
| `step_count` | `int` | `≥ 0` | Current step number in the episode |

### Observation JSON Example
```json
{
  "open_ports": [22, 80, 3389],
  "threat_level": 0.42,
  "traffic": 320,
  "blocked_ips": ["192.168.1.100"],
  "active_attacks": 2,
  "vulnerabilities": 3,
  "breach_detected": false,
  "step_count": 5
}
```

---

## 💰 Reward Structure

| Action Result | Reward |
|---------------|--------|
| Successfully block an attacking IP | `+1.5` |
| Patch a vulnerability (close a port) | `+0.8` |
| Scan reveals new threat | `+0.4` |
| Scan with no new threats | `+0.2` |
| Block an IP that is not an active attacker | `+0.1` |
| Block an already-blocked IP (wasted action) | `-0.1` |
| No active attacks but tries to block | `-0.2` |
| Breach detected (threat_level > 0.85) | Heavy implicit penalty |
| Missed attack increments | Threat level escalation |

Reward returned from `step()` is a **float** value.

---

## 🎯 Task Descriptions

### Task 1 — Easy: Basic Threat Response
- **Goal:** Block at least **2 attacks** within **30 steps**
- **Starting State:** 3–5 open ports, moderate threat level (0.1–0.4)
- **Termination:** 30 steps elapsed
- **Success Threshold:** Score ≥ 0.5

### Task 2 — Medium: Advanced Perimeter Defense
- **Goal:** Block at least **4 attacks** AND reduce open ports by **2+** within **40 steps**
- **Starting State:** 5–7 open ports, elevated threat level
- **Termination:** 40 steps elapsed
- **Success Threshold:** Score ≥ 0.6

### Task 3 — Hard: Zero-Breach Incident Response
- **Goal:** Block at least **6 attacks** with **zero system breaches** within **50 steps**
- **Starting State:** 7–10 open ports, high threat level
- **Termination:** 50 steps elapsed OR breach detected
- **Success Threshold:** Score ≥ 0.7

---

## 🏆 Grading

All scores are **deterministic** and in the range `[0.0, 1.0]` with partial credit.

### Easy Grader
```
score = (min(blocks/2, 1.0) × 0.70)
      + ((1 - threat_level) × 0.15)
      + (no_breach_bonus × 0.15)
```

### Medium Grader
```
score = (min(blocks/4, 1.0) × 0.50)
      + (min(patches/2, 1.0) × 0.30)
      + ((1 - threat_level) × 0.10)
      + (no_breach_bonus × 0.10)
```

### Hard Grader
```
score = (min(blocks/6, 1.0) × 0.60)
      + (no_breach_bonus × 0.30)
      + ((1 - threat_level) × 0.10)
      - (missed_attacks × 0.05, capped at 0.30)
```

---

## ⚙️ Setup Instructions

### Prerequisites
- Python 3.10+
- pip

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Environment Variables
```bash
export API_BASE_URL="https://api.openai.com/v1"   # or any OpenAI-compatible endpoint
export MODEL_NAME="gpt-4o-mini"                    # model to use
export HF_TOKEN="hf_your_token_here"               # Hugging Face / API key
```

---

## 🐳 Running with Docker

### Build the Image
```bash
docker build -t openenv-cybersoc .
```

### Run the Container
```bash
docker run -p 7860:7860 \
  -e API_BASE_URL="https://api.openai.com/v1" \
  -e MODEL_NAME="gpt-4o-mini" \
  -e HF_TOKEN="your_token_here" \
  openenv-cybersoc
```

The API will be available at `http://localhost:7860`.

---

## 🚀 Running the FastAPI Server

```bash
uvicorn app:app --host 0.0.0.0 --port 7860
```

Or directly:
```bash
python app.py
```

### Interactive API Docs
Visit `http://localhost:7860/docs` for the Swagger UI.

---

## 🤖 How to Run Inference

Set your environment variables first, then:

```bash
python inference.py
```

The inference script will:
1. Test API connectivity (falls back to rule-based agent if unavailable)
2. Run all 3 tasks (easy → medium → hard)
3. Print step-by-step progress for each task
4. Print final scores and average score

### Sample Output
```
============================================================
  OpenEnv CyberSOC — Inference Runner
  Model    : gpt-4o-mini
  API Base : https://api.openai.com/v1
============================================================

  ✓ LLM API connected successfully

============================================================
  TASK: Basic Threat Response [EASY]
  Max Steps: 30 | Goal: Block at least 2 attacks...
============================================================
  Step   5 | Action: block_ip   | Reward: +1.50 | Total: +2.30 | Blocks: 1 | Breach: False
  Step  10 | Action: patch      | Reward: +0.80 | Total: +4.20 | Blocks: 2 | Breach: False
  ...
  ── GRADE SCORE  : 0.8250 ──

============================================================
  FINAL SCORES
============================================================
  EASY    : 0.8250  |████████████████    |
  MEDIUM  : 0.6100  |████████████        |
  HARD    : 0.4800  |█████████           |

  AVERAGE SCORE : 0.6383
============================================================
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API info and available endpoints |
| `GET` | `/health` | Health check |
| `POST` | `/reset` | Reset environment, returns initial `Observation` |
| `POST` | `/step` | Execute one action step, returns `StepResult` |
| `GET` | `/state` | Full internal environment state |
| `GET` | `/grade` | Current episode grade score `[0.0, 1.0]` |
| `GET` | `/tasks` | List all available tasks |
| `GET` | `/tasks/{difficulty}` | Get task details by difficulty |

### POST /reset
```bash
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"difficulty": "easy", "seed": 42}'
```

### POST /step
```bash
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"action_type": "block_ip", "target_ip": "192.168.1.100", "difficulty": "easy"}'
```

### GET /state
```bash
curl http://localhost:7860/state?difficulty=easy
```

### GET /grade
```bash
curl http://localhost:7860/grade?difficulty=easy
```

---

## 📊 Expected Baseline Scores

Scores achieved by the **rule-based fallback agent** (no LLM required):

| Task | Difficulty | Expected Score | Notes |
|------|------------|----------------|-------|
| Basic Threat Response | Easy | `0.75 – 0.90` | Simple heuristics work well |
| Advanced Perimeter Defense | Medium | `0.55 – 0.70` | Requires balanced blocking + patching |
| Zero-Breach Incident Response | Hard | `0.40 – 0.60` | Breach-avoidance is challenging |
| **Average** | — | **`0.57 – 0.73`** | |

With an LLM agent and proper prompting, scores can reach:

| Task | Expected Score |
|------|----------------|
| Easy | `0.80 – 0.95` |
| Medium | `0.65 – 0.80` |
| Hard | `0.50 – 0.70` |

---

## 📁 Project Structure

```
openenv-cybersoc/
├── env/
│   ├── __init__.py          # Package exports
│   ├── models.py            # Pydantic models (Observation, Action, Reward, StepResult)
│   ├── environment.py       # CyberSOCEnvironment (step, reset, state)
│   ├── tasks.py             # Task definitions (easy/medium/hard)
│   └── graders.py           # Deterministic graders with partial scoring
├── inference.py             # LLM inference script (runs all 3 tasks)
├── app.py                   # FastAPI application (port 7860)
├── openenv.yaml             # OpenEnv specification
├── Dockerfile               # Production Docker build
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

---

## 📜 License

MIT License — Free to use, modify, and distribute.

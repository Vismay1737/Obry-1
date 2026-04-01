import random
import time
from typing import Tuple, Dict, Any, List, Optional
from env.models import Observation, Action, Reward, StepResult


ATTACK_IPS = [
    "192.168.1.100", "10.0.0.50", "172.16.0.200", "203.0.113.42",
    "198.51.100.77", "192.0.2.99", "185.220.101.1", "185.220.101.2",
    "45.33.32.156", "104.21.14.101", "1.234.56.78", "91.108.4.100",
]

VULNERABLE_PORTS = [21, 22, 23, 25, 80, 443, 3389, 8080, 8443, 3306]
SAFE_PORTS = [53, 123, 161, 111]


class CyberSOCEnvironment:
    """
    Cybersecurity SOC (Security Operations Center) environment.
    An agent defends a system from incoming attacks.
    """

    def __init__(self, max_steps: int = 50, difficulty: str = "easy", seed: Optional[int] = None):
        self.max_steps = max_steps
        self.difficulty = difficulty
        self.seed = seed
        self._rng = random.Random(seed)

        # Internal state
        self._step_count: int = 0
        self._open_ports: List[int] = []
        self._blocked_ips: List[str] = []
        self._active_attack_ips: List[str] = []
        self._threat_level: float = 0.0
        self._traffic: int = 0
        self._vulnerabilities: int = 0
        self._breach_detected: bool = False
        self._attacks_blocked: int = 0
        self._missed_attacks: int = 0
        self._patches_applied: int = 0
        self._done: bool = False

    def reset(self) -> Observation:
        """Reset environment to initial state and return initial observation."""
        self._rng = random.Random(self.seed)
        self._step_count = 0
        self._blocked_ips = []
        self._attacks_blocked = 0
        self._missed_attacks = 0
        self._patches_applied = 0
        self._breach_detected = False
        self._done = False

        # Initialize open ports based on difficulty
        if self.difficulty == "easy":
            port_count = self._rng.randint(3, 5)
            self._vulnerabilities = self._rng.randint(2, 4)
        elif self.difficulty == "medium":
            port_count = self._rng.randint(5, 7)
            self._vulnerabilities = self._rng.randint(4, 6)
        else:  # hard
            port_count = self._rng.randint(7, 10)
            self._vulnerabilities = self._rng.randint(6, 9)

        self._open_ports = self._rng.sample(VULNERABLE_PORTS, min(port_count, len(VULNERABLE_PORTS)))
        self._threat_level = self._rng.uniform(0.1, 0.4)
        self._traffic = self._rng.randint(100, 500)
        self._active_attack_ips = self._rng.sample(ATTACK_IPS, min(3, len(ATTACK_IPS)))

        return self._get_observation()

    def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        """Execute one step in the environment."""
        if self._done:
            obs = self._get_observation()
            return obs, 0.0, True, {"error": "Episode already done. Call reset()."}

        self._step_count += 1
        reward_obj = self._process_action(action)

        # Simulate environment evolution
        self._evolve_environment()

        # Check termination conditions
        if self._step_count >= self.max_steps:
            self._done = True
        if self._breach_detected and self.difficulty == "hard":
            self._done = True

        obs = self._get_observation()
        info = {
            "step": self._step_count,
            "attacks_blocked": self._attacks_blocked,
            "missed_attacks": self._missed_attacks,
            "patches_applied": self._patches_applied,
            "breach_detected": self._breach_detected,
            "reward_reason": reward_obj.reason,
            "action_type": action.action_type,
        }

        return obs, reward_obj.value, self._done, info

    def state(self) -> Dict[str, Any]:
        """Return full internal state."""
        return {
            "step_count": self._step_count,
            "open_ports": self._open_ports,
            "blocked_ips": self._blocked_ips,
            "active_attack_ips": self._active_attack_ips,
            "threat_level": self._threat_level,
            "traffic": self._traffic,
            "vulnerabilities": self._vulnerabilities,
            "breach_detected": self._breach_detected,
            "attacks_blocked": self._attacks_blocked,
            "missed_attacks": self._missed_attacks,
            "patches_applied": self._patches_applied,
            "done": self._done,
            "difficulty": self.difficulty,
            "max_steps": self.max_steps,
        }

    def _get_observation(self) -> Observation:
        return Observation(
            open_ports=list(self._open_ports),
            threat_level=round(self._threat_level, 3),
            traffic=self._traffic,
            blocked_ips=list(self._blocked_ips),
            active_attacks=len(self._active_attack_ips),
            vulnerabilities=self._vulnerabilities,
            breach_detected=self._breach_detected,
            step_count=self._step_count,
        )

    def _process_action(self, action: Action) -> Reward:
        """Process the agent's action and compute reward."""
        if action.action_type == "block_ip":
            return self._handle_block_ip(action)
        elif action.action_type == "scan":
            return self._handle_scan(action)
        elif action.action_type == "patch":
            return self._handle_patch(action)
        else:
            return Reward(
                value=-0.5,
                reason="Unknown action type",
                action_taken=str(action.action_type),
            )

    def _handle_block_ip(self, action: Action) -> Reward:
        target_ip = action.target_ip

        if not target_ip:
            # Default: block the most threatening active attack IP
            if self._active_attack_ips:
                target_ip = self._active_attack_ips[0]
            else:
                return Reward(
                    value=-0.2,
                    reason="No target IP specified and no active attacks",
                    action_taken="block_ip",
                )

        if target_ip in self._blocked_ips:
            return Reward(
                value=-0.1,
                reason=f"IP {target_ip} is already blocked (wasted action)",
                action_taken="block_ip",
            )

        self._blocked_ips.append(target_ip)

        if target_ip in self._active_attack_ips:
            self._active_attack_ips.remove(target_ip)
            self._attacks_blocked += 1
            self._threat_level = max(0.0, self._threat_level - 0.15)
            return Reward(
                value=1.5,
                reason=f"Successfully blocked attacking IP {target_ip}",
                action_taken="block_ip",
                blocked_attack=True,
            )
        else:
            return Reward(
                value=0.1,
                reason=f"Blocked IP {target_ip} (not an active attacker — precautionary)",
                action_taken="block_ip",
            )

    def _handle_scan(self, action: Action) -> Reward:
        # Scan reveals hidden threats
        hidden_attackers = [ip for ip in ATTACK_IPS
                            if ip not in self._active_attack_ips
                            and ip not in self._blocked_ips]

        if hidden_attackers and self._rng.random() < 0.6:
            found_ip = self._rng.choice(hidden_attackers)
            self._active_attack_ips.append(found_ip)
            self._threat_level = min(1.0, self._threat_level + 0.05)
            return Reward(
                value=0.4,
                reason=f"Scan revealed new threat from {found_ip}",
                action_taken="scan",
            )
        else:
            return Reward(
                value=0.2,
                reason="Scan completed, system monitoring improved",
                action_taken="scan",
            )

    def _handle_patch(self, action: Action) -> Reward:
        if self._vulnerabilities <= 0:
            return Reward(
                value=-0.1,
                reason="No vulnerabilities to patch (wasted action)",
                action_taken="patch",
            )

        port_to_remove = action.port
        if port_to_remove and port_to_remove in self._open_ports:
            self._open_ports.remove(port_to_remove)
        elif self._open_ports:
            # Auto-patch: close the riskiest open port
            port_to_remove = self._open_ports[0]
            self._open_ports.remove(port_to_remove)

        self._vulnerabilities = max(0, self._vulnerabilities - 1)
        self._patches_applied += 1
        self._threat_level = max(0.0, self._threat_level - 0.1)

        return Reward(
            value=0.8,
            reason=f"Successfully patched vulnerability (closed port {port_to_remove})",
            action_taken="patch",
        )

    def _evolve_environment(self):
        """Simulate environment changes each step."""
        # New attacks may spawn
        available_ips = [ip for ip in ATTACK_IPS
                         if ip not in self._active_attack_ips
                         and ip not in self._blocked_ips]

        spawn_chance = 0.2 if self.difficulty == "easy" else (0.35 if self.difficulty == "medium" else 0.5)
        if available_ips and self._rng.random() < spawn_chance:
            new_attacker = self._rng.choice(available_ips)
            self._active_attack_ips.append(new_attacker)
            self._threat_level = min(1.0, self._threat_level + 0.08)

        # Missed attacks increase threat and may cause breach
        if self._active_attack_ips:
            breach_chance = len(self._active_attack_ips) * 0.05 * (1 + self._vulnerabilities * 0.05)
            if self._rng.random() < breach_chance:
                self._missed_attacks += 1
                self._threat_level = min(1.0, self._threat_level + 0.12)
                if self._threat_level > 0.85:
                    self._breach_detected = True

        # Traffic fluctuates
        self._traffic = max(0, self._traffic + self._rng.randint(-50, 100))

        # Threat decays slightly if no active attacks
        if not self._active_attack_ips:
            self._threat_level = max(0.0, self._threat_level - 0.03)

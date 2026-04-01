from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class Observation(BaseModel):
    open_ports: List[int] = Field(default_factory=list, description="List of currently open ports on the system")
    threat_level: float = Field(default=0.0, ge=0.0, le=1.0, description="Current threat level (0.0 = safe, 1.0 = critical)")
    traffic: int = Field(default=0, ge=0, description="Current network traffic volume in requests/sec")
    blocked_ips: List[str] = Field(default_factory=list, description="List of currently blocked IP addresses")
    active_attacks: int = Field(default=0, ge=0, description="Number of currently active attack attempts")
    vulnerabilities: int = Field(default=0, ge=0, description="Number of known unpatched vulnerabilities")
    breach_detected: bool = Field(default=False, description="Whether a system breach has been detected")
    step_count: int = Field(default=0, ge=0, description="Current step number in the episode")


class Action(BaseModel):
    action_type: Literal["block_ip", "scan", "patch"] = Field(
        description="Type of defensive action to take"
    )
    target_ip: Optional[str] = Field(default=None, description="IP address to block (required for block_ip)")
    port: Optional[int] = Field(default=None, description="Port to patch (optional for patch action)")

    class Config:
        use_enum_values = True


class Reward(BaseModel):
    value: float = Field(description="Numerical reward value (positive = good, negative = bad)")
    reason: str = Field(description="Human-readable explanation for the reward")
    action_taken: str = Field(description="The action that generated this reward")
    blocked_attack: bool = Field(default=False, description="Whether an attack was successfully blocked")
    breach_penalty: bool = Field(default=False, description="Whether a breach penalty was applied")


class StepResult(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: dict

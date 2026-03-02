"""
Shared data models for the SOP Autopilot engine.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any


class StepType(str, Enum):
    """Classification of workflow step types."""

    AUTO = "AUTO"  # System can handle automatically
    HUMAN = "HUMAN"  # Requires human judgment or action
    DECISION = "DECISION"  # Branch point in the workflow
    START = "START"  # Entry point
    END = "END"  # Terminal point


@dataclass
class Step:
    """A single step in a workflow graph."""

    id: str
    title: str
    description: str
    step_type: StepType
    owner: str = "System"
    next_steps: list[str] = field(default_factory=list)
    branches: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.step_type.value,
            "owner": self.owner,
            "next_steps": self.next_steps,
            "branches": self.branches,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Step":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            step_type=StepType(data["type"]),
            owner=data.get("owner", "System"),
            next_steps=data.get("next_steps", []),
            branches=data.get("branches", {}),
        )


@dataclass
class Workflow:
    """A complete workflow graph parsed from an SOP."""

    name: str
    description: str
    source_format: str  # "text", "bpmn", "visio"
    steps: dict[str, Step] = field(default_factory=dict)
    start_step_id: str = ""

    def get_start_step(self) -> Optional[Step]:
        """Find the starting step of the workflow."""
        if self.start_step_id and self.start_step_id in self.steps:
            return self.steps[self.start_step_id]
        # Find step with START type
        for step in self.steps.values():
            if step.step_type == StepType.START:
                return step
        # Fall back to first step
        if self.steps:
            return list(self.steps.values())[0]
        return None

    def get_step(self, step_id: str) -> Optional[Step]:
        return self.steps.get(step_id)

    def get_stats(self) -> dict:
        """Return summary statistics about the workflow."""
        type_counts = {}
        for step in self.steps.values():
            t = step.step_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        owners = set(s.owner for s in self.steps.values())
        return {
            "total_steps": len(self.steps),
            "type_counts": type_counts,
            "owners": sorted(owners),
            "decision_points": type_counts.get("DECISION", 0),
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "source_format": self.source_format,
            "start_step_id": self.start_step_id,
            "steps": [s.to_dict() for s in self.steps.values()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Workflow":
        wf = cls(
            name=data["name"],
            description=data["description"],
            source_format=data.get("source_format", "text"),
            start_step_id=data.get("start_step_id", ""),
        )
        for step_data in data.get("steps", []):
            step = Step.from_dict(step_data)
            wf.steps[step.id] = step
        return wf


@dataclass
class CaseState:
    """Tracks the execution state of a workflow case."""

    case_id: str
    client_data: dict = field(default_factory=dict)
    current_step_id: str = ""
    completed_steps: list[str] = field(default_factory=list)
    decisions_made: dict[str, str] = field(default_factory=dict)
    step_results: dict[str, dict] = field(default_factory=dict)
    status: str = "in_progress"  # in_progress, completed, blocked, failed

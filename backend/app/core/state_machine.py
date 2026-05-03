"""
Work Item State Machine — State design pattern.

Encapsulates valid transitions and guards for each state.
Attempting an invalid transition raises a ValueError.
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class WorkItemState(ABC):
    """Abstract base for all work item states."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def can_transition_to(self, target: str) -> bool:
        ...

    def transition_to(self, target: str) -> "WorkItemState":
        if not self.can_transition_to(target):
            raise ValueError(
                f"Invalid transition: {self.name} → {target}. "
                f"Allowed: {self.allowed_transitions}"
            )
        return STATE_MAP[target]()

    @property
    @abstractmethod
    def allowed_transitions(self) -> list[str]:
        ...

    def __str__(self) -> str:
        return self.name


class OpenState(WorkItemState):
    @property
    def name(self) -> str:
        return "OPEN"

    @property
    def allowed_transitions(self) -> list[str]:
        return ["INVESTIGATING"]

    def can_transition_to(self, target: str) -> bool:
        return target in self.allowed_transitions


class InvestigatingState(WorkItemState):
    @property
    def name(self) -> str:
        return "INVESTIGATING"

    @property
    def allowed_transitions(self) -> list[str]:
        return ["RESOLVED", "OPEN"]  # allow re-open

    def can_transition_to(self, target: str) -> bool:
        return target in self.allowed_transitions


class ResolvedState(WorkItemState):
    @property
    def name(self) -> str:
        return "RESOLVED"

    @property
    def allowed_transitions(self) -> list[str]:
        return ["CLOSED", "INVESTIGATING"]  # allow re-investigation

    def can_transition_to(self, target: str) -> bool:
        return target in self.allowed_transitions


class ClosedState(WorkItemState):
    """Terminal state — no further transitions."""

    @property
    def name(self) -> str:
        return "CLOSED"

    @property
    def allowed_transitions(self) -> list[str]:
        return []

    def can_transition_to(self, target: str) -> bool:
        return False


STATE_MAP: dict[str, type[WorkItemState]] = {
    "OPEN": OpenState,
    "INVESTIGATING": InvestigatingState,
    "RESOLVED": ResolvedState,
    "CLOSED": ClosedState,
}


def get_state(status: str) -> WorkItemState:
    """Deserialise a status string back to a state object."""
    if status not in STATE_MAP:
        raise ValueError(f"Unknown status: {status}")
    return STATE_MAP[status]()


def validate_transition(current_status: str, target_status: str) -> None:
    """Raises ValueError on illegal transitions."""
    state = get_state(current_status)
    state.transition_to(target_status)  # raises if invalid

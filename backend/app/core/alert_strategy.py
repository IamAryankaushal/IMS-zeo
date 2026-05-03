"""
Alerting Strategy — Strategy design pattern.

Different component types trigger different alert priorities.
New strategies can be added without modifying existing code (Open/Closed).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AlertContext:
    component_id: str
    component_type: str
    signal_count: int
    error_type: str


class AlertStrategy(ABC):
    @abstractmethod
    def get_priority(self, ctx: AlertContext) -> str:
        """Return priority string: P0, P1, P2, P3."""

    @abstractmethod
    def get_title(self, ctx: AlertContext) -> str:
        """Return human-readable work item title."""

    @abstractmethod
    def notify(self, ctx: AlertContext, priority: str) -> None:
        """Send the alert (log, webhook, PagerDuty, etc.)."""


class RDBMSFailureStrategy(AlertStrategy):
    """Database failures are always P0 — critical path."""

    def get_priority(self, ctx: AlertContext) -> str:
        return "P0"

    def get_title(self, ctx: AlertContext) -> str:
        return f"[P0] RDBMS Failure — {ctx.component_id}"

    def notify(self, ctx: AlertContext, priority: str) -> None:
        logger.critical(
            "P0 ALERT | component=%s | signals=%d | error=%s",
            ctx.component_id, ctx.signal_count, ctx.error_type
        )


class CacheFailureStrategy(AlertStrategy):
    """Cache failures degrade performance but are not fatal — P2."""

    def get_priority(self, ctx: AlertContext) -> str:
        return "P2"

    def get_title(self, ctx: AlertContext) -> str:
        return f"[P2] Cache Degradation — {ctx.component_id}"

    def notify(self, ctx: AlertContext, priority: str) -> None:
        logger.warning(
            "P2 ALERT | component=%s | signals=%d | error=%s",
            ctx.component_id, ctx.signal_count, ctx.error_type
        )


class QueueFailureStrategy(AlertStrategy):
    """Queue failures can cascade — P1."""

    def get_priority(self, ctx: AlertContext) -> str:
        return "P1"

    def get_title(self, ctx: AlertContext) -> str:
        return f"[P1] Queue Failure — {ctx.component_id}"

    def notify(self, ctx: AlertContext, priority: str) -> None:
        logger.error(
            "P1 ALERT | component=%s | signals=%d | error=%s",
            ctx.component_id, ctx.signal_count, ctx.error_type
        )


class APIFailureStrategy(AlertStrategy):
    """API failures — P1 by default."""

    def get_priority(self, ctx: AlertContext) -> str:
        return "P1"

    def get_title(self, ctx: AlertContext) -> str:
        return f"[P1] API Failure — {ctx.component_id}"

    def notify(self, ctx: AlertContext, priority: str) -> None:
        logger.error(
            "P1 ALERT | component=%s | signals=%d | error=%s",
            ctx.component_id, ctx.signal_count, ctx.error_type
        )


class DefaultFailureStrategy(AlertStrategy):
    """Catch-all for unknown component types — P3."""

    def get_priority(self, ctx: AlertContext) -> str:
        return "P3"

    def get_title(self, ctx: AlertContext) -> str:
        return f"[P3] Degradation — {ctx.component_id}"

    def notify(self, ctx: AlertContext, priority: str) -> None:
        logger.info(
            "P3 ALERT | component=%s | signals=%d | error=%s",
            ctx.component_id, ctx.signal_count, ctx.error_type
        )


# Strategy registry — maps component type prefixes to strategies
_STRATEGY_REGISTRY: dict[str, AlertStrategy] = {
    "RDBMS": RDBMSFailureStrategy(),
    "DB": RDBMSFailureStrategy(),
    "POSTGRES": RDBMSFailureStrategy(),
    "MYSQL": RDBMSFailureStrategy(),
    "CACHE": CacheFailureStrategy(),
    "REDIS": CacheFailureStrategy(),
    "MEMCACHE": CacheFailureStrategy(),
    "QUEUE": QueueFailureStrategy(),
    "KAFKA": QueueFailureStrategy(),
    "RABBIT": QueueFailureStrategy(),
    "SQS": QueueFailureStrategy(),
    "API": APIFailureStrategy(),
    "MCP": APIFailureStrategy(),
    "SERVICE": APIFailureStrategy(),
}


def resolve_strategy(component_id: str) -> AlertStrategy:
    """
    Pick the right alert strategy from the component ID.
    e.g. 'CACHE_CLUSTER_01' → CacheFailureStrategy
    """
    upper = component_id.upper()
    for prefix, strategy in _STRATEGY_REGISTRY.items():
        if upper.startswith(prefix) or f"_{prefix}_" in upper or upper.endswith(f"_{prefix}"):
            return strategy
    return DefaultFailureStrategy()

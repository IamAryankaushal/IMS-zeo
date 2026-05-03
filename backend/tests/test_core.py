"""
Unit tests for:
- RCA validation logic (Pydantic schema)
- State machine transitions
- Alert strategy selection
- Rate limiter
- Debounce logic
"""
import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from app.core.alert_strategy import resolve_strategy, AlertContext
from app.core.rate_limiter import TokenBucket
from app.core.state_machine import (
    get_state, validate_transition, ClosedState, OpenState,
    InvestigatingState, ResolvedState
)
from app.models.schemas import RCACreateRequest


# ── State Machine ─────────────────────────────────────────────────────────────

class TestStateMachine:
    def test_open_to_investigating(self):
        state = get_state("OPEN")
        next_state = state.transition_to("INVESTIGATING")
        assert next_state.name == "INVESTIGATING"

    def test_investigating_to_resolved(self):
        state = get_state("INVESTIGATING")
        next_state = state.transition_to("RESOLVED")
        assert next_state.name == "RESOLVED"

    def test_resolved_to_closed(self):
        state = get_state("RESOLVED")
        next_state = state.transition_to("CLOSED")
        assert next_state.name == "CLOSED"

    def test_invalid_open_to_closed(self):
        with pytest.raises(ValueError, match="Invalid transition"):
            validate_transition("OPEN", "CLOSED")

    def test_invalid_open_to_resolved(self):
        with pytest.raises(ValueError, match="Invalid transition"):
            validate_transition("OPEN", "RESOLVED")

    def test_closed_is_terminal(self):
        state = get_state("CLOSED")
        assert state.allowed_transitions == []
        with pytest.raises(ValueError, match="Invalid transition"):
            state.transition_to("OPEN")

    def test_can_reopen_from_investigating(self):
        state = get_state("INVESTIGATING")
        next_state = state.transition_to("OPEN")
        assert next_state.name == "OPEN"

    def test_full_lifecycle(self):
        validate_transition("OPEN", "INVESTIGATING")
        validate_transition("INVESTIGATING", "RESOLVED")
        validate_transition("RESOLVED", "CLOSED")

    def test_state_string_representation(self):
        assert str(OpenState()) == "OPEN"
        assert str(ClosedState()) == "CLOSED"


# ── RCA Validation ────────────────────────────────────────────────────────────

class TestRCAValidation:
    def _valid_rca(self, **overrides):
        now = datetime.now(timezone.utc)
        base = dict(
            incident_start=now - timedelta(hours=2),
            incident_end=now,
            root_cause_category="SOFTWARE_BUG",
            root_cause_description="Memory leak in connection pool caused OOM",
            fix_applied="Deployed hotfix v1.2.3 to restart the pool",
            prevention_steps="Add memory profiling to CI pipeline",
            submitted_by="engineer",
        )
        base.update(overrides)
        return base

    def test_valid_rca_passes(self):
        rca = RCACreateRequest(**self._valid_rca())
        assert rca.root_cause_category == "SOFTWARE_BUG"

    def test_end_before_start_fails(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(Exception, match="incident_end must be after"):
            RCACreateRequest(**self._valid_rca(
                incident_start=now,
                incident_end=now - timedelta(hours=1),
            ))

    def test_equal_start_end_fails(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(Exception):
            RCACreateRequest(**self._valid_rca(incident_start=now, incident_end=now))

    def test_short_description_fails(self):
        with pytest.raises(Exception):
            RCACreateRequest(**self._valid_rca(root_cause_description="short"))

    def test_short_fix_applied_fails(self):
        with pytest.raises(Exception):
            RCACreateRequest(**self._valid_rca(fix_applied="ok"))

    def test_short_prevention_fails(self):
        with pytest.raises(Exception):
            RCACreateRequest(**self._valid_rca(prevention_steps="maybe"))

    def test_invalid_category_fails(self):
        with pytest.raises(Exception):
            RCACreateRequest(**self._valid_rca(root_cause_category="ALIENS"))

    def test_all_valid_categories(self):
        categories = [
            "HARDWARE_FAILURE", "SOFTWARE_BUG", "CONFIGURATION_ERROR",
            "CAPACITY_EXHAUSTION", "NETWORK_ISSUE", "HUMAN_ERROR",
            "THIRD_PARTY_DEPENDENCY", "UNKNOWN"
        ]
        for cat in categories:
            rca = RCACreateRequest(**self._valid_rca(root_cause_category=cat))
            assert rca.root_cause_category == cat


# ── Alert Strategy ────────────────────────────────────────────────────────────

class TestAlertStrategy:
    def _ctx(self, component_id: str) -> AlertContext:
        return AlertContext(
            component_id=component_id,
            component_type="UNKNOWN",
            signal_count=1,
            error_type="TEST",
        )

    def test_rdbms_is_p0(self):
        strategy = resolve_strategy("RDBMS_PRIMARY_01")
        assert strategy.get_priority(self._ctx("RDBMS_PRIMARY_01")) == "P0"

    def test_postgres_is_p0(self):
        strategy = resolve_strategy("POSTGRES_REPLICA")
        assert strategy.get_priority(self._ctx("POSTGRES_REPLICA")) == "P0"

    def test_cache_is_p2(self):
        strategy = resolve_strategy("CACHE_CLUSTER_01")
        assert strategy.get_priority(self._ctx("CACHE_CLUSTER_01")) == "P2"

    def test_redis_is_p2(self):
        strategy = resolve_strategy("REDIS_SENTINEL")
        assert strategy.get_priority(self._ctx("REDIS_SENTINEL")) == "P2"

    def test_queue_is_p1(self):
        strategy = resolve_strategy("KAFKA_BROKER_01")
        assert strategy.get_priority(self._ctx("KAFKA_BROKER_01")) == "P1"

    def test_api_is_p1(self):
        strategy = resolve_strategy("API_GATEWAY")
        assert strategy.get_priority(self._ctx("API_GATEWAY")) == "P1"

    def test_mcp_is_p1(self):
        strategy = resolve_strategy("MCP_HOST_01")
        assert strategy.get_priority(self._ctx("MCP_HOST_01")) == "P1"

    def test_unknown_is_p3(self):
        strategy = resolve_strategy("UNKNOWN_COMPONENT_XYZ")
        assert strategy.get_priority(self._ctx("UNKNOWN_COMPONENT_XYZ")) == "P3"

    def test_title_contains_component(self):
        strategy = resolve_strategy("CACHE_CLUSTER_01")
        title = strategy.get_title(self._ctx("CACHE_CLUSTER_01"))
        assert "CACHE_CLUSTER_01" in title


# ── Rate Limiter ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRateLimiter:
    async def test_allows_within_capacity(self):
        bucket = TokenBucket(capacity=10, refill_rate=10)
        for _ in range(10):
            assert await bucket.consume(1) is True

    async def test_blocks_when_full(self):
        bucket = TokenBucket(capacity=5, refill_rate=5)
        for _ in range(5):
            await bucket.consume(1)
        assert await bucket.consume(1) is False

    async def test_refills_over_time(self):
        bucket = TokenBucket(capacity=10, refill_rate=1000)
        for _ in range(10):
            await bucket.consume(1)
        await asyncio.sleep(0.02)  # 20ms → ~20 tokens refilled at 1000/s
        assert await bucket.consume(1) is True

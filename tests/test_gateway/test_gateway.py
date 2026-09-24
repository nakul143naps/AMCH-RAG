"""Comprehensive tests for Phase 11 Multi-Provider Model Gateway.

Verifies:
- Priority failover: Primary (Gemini) -> Secondary (Groq) -> Tertiary (OpenRouter).
- Bounded retries per provider with exponential backoff.
- CircuitBreaker tripping (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
- Purpose-based dispatching (`generate`, `grade`, `route`, `check_groundedness`, `rewrite_query`).
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.gateway.circuit_breaker import CircuitBreaker
from app.gateway.client import ModelGateway


def test_circuit_breaker_lifecycle():
    """Verify circuit breaker transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    breaker = CircuitBreaker(provider_name="test_provider", failure_threshold=2, cooldown_seconds=0.1)
    assert breaker.state == "CLOSED"
    assert breaker.can_execute() is True

    # First failure - below threshold
    breaker.record_failure("HTTP 500")
    assert breaker.state == "CLOSED"
    assert breaker.consecutive_failures == 1
    assert breaker.can_execute() is True

    # Second failure - reaches threshold -> trips to OPEN
    breaker.record_failure("HTTP 500")
    assert breaker.state == "OPEN"
    assert breaker.can_execute() is False

    # Wait for cooldown to expire
    import time
    time.sleep(0.12)

    # Cooldown expired -> transitions to HALF_OPEN trial
    assert breaker.can_execute() is True
    assert breaker.state == "HALF_OPEN"

    # Successful trial request resets to CLOSED
    breaker.record_success()
    assert breaker.state == "CLOSED"
    assert breaker.consecutive_failures == 0


@pytest.mark.asyncio
async def test_gateway_primary_gemini_success():
    """When Gemini is healthy, it is invoked as primary provider."""
    settings = Settings(
        GEMINI_API_KEY="test_key",
        GROQ_API_KEY="test_key",
        OPENROUTER_API_KEY="test_key",
        PROVIDER_PRIORITY=["gemini", "groq", "openrouter"],
    )
    gateway = ModelGateway(settings=settings)

    with patch.object(gateway.providers["gemini"], "generate_text", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = "Gemini answer"
        text, provider = await gateway.generate(prompt="Hello", purpose="generation")

        assert text == "Gemini answer"
        assert provider == "gemini"
        mock_gemini.assert_called_once()


@pytest.mark.asyncio
async def test_gateway_failover_gemini_to_groq_on_429():
    """When Gemini fails with 429/error, gateway transparently falls over to Groq."""
    settings = Settings(
        GEMINI_API_KEY="test_key",
        GROQ_API_KEY="test_key",
        OPENROUTER_API_KEY="test_key",
        PROVIDER_PRIORITY=["gemini", "groq", "openrouter"],
    )
    gateway = ModelGateway(settings=settings)

    with (
        patch.object(
            gateway.providers["gemini"],
            "generate_text",
            new_callable=AsyncMock,
            side_effect=RuntimeError("429 Resource Exhausted"),
        ) as mock_gemini,
        patch.object(
            gateway.providers["groq"],
            "generate_text",
            new_callable=AsyncMock,
            return_value="Groq fallback answer",
        ) as mock_groq,
    ):
        text, provider = await gateway.generate(
            prompt="Compute distributed hash",
            purpose="generation",
            max_retries_per_provider=2,
        )

        assert text == "Groq fallback answer"
        assert provider == "groq"
        assert mock_gemini.call_count == 2
        mock_groq.assert_called_once()
        assert gateway.failover_counts["gemini"] == 2


@pytest.mark.asyncio
async def test_gateway_failover_to_openrouter_when_gemini_and_groq_fail():
    """When both Gemini and Groq fail, gateway falls through to OpenRouter."""
    settings = Settings(
        GEMINI_API_KEY="test_key",
        GROQ_API_KEY="test_key",
        OPENROUTER_API_KEY="test_key",
        PROVIDER_PRIORITY=["gemini", "groq", "openrouter"],
    )
    gateway = ModelGateway(settings=settings)

    with (
        patch.object(
            gateway.providers["gemini"],
            "generate_text",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Gemini Outage"),
        ),
        patch.object(
            gateway.providers["groq"],
            "generate_text",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Groq Rate Limited"),
        ),
        patch.object(
            gateway.providers["openrouter"],
            "generate_text",
            new_callable=AsyncMock,
            return_value="OpenRouter tertiary answer",
        ) as mock_openrouter,
    ):
        text, provider = await gateway.generate(
            prompt="Analyze system logs",
            purpose="generation",
            max_retries_per_provider=1,
        )

        assert text == "OpenRouter tertiary answer"
        assert provider == "openrouter"
        mock_openrouter.assert_called_once()


@pytest.mark.asyncio
async def test_gateway_circuit_breaker_bypasses_tripped_provider():
    """When a provider's circuit breaker is OPEN, gateway skips it immediately without making calls."""
    settings = Settings(
        GEMINI_API_KEY="test_key",
        GROQ_API_KEY="test_key",
        PROVIDER_PRIORITY=["gemini", "groq"],
    )
    gateway = ModelGateway(settings=settings)

    # Manually trip Gemini circuit breaker
    gemini_breaker = gateway.circuit_breakers["gemini"]
    gemini_breaker.record_failure("error 1")
    gemini_breaker.record_failure("error 2")
    gemini_breaker.record_failure("error 3")
    assert gemini_breaker.state == "OPEN"

    with (
        patch.object(gateway.providers["gemini"], "generate_text", new_callable=AsyncMock) as mock_gemini,
        patch.object(
            gateway.providers["groq"],
            "generate_text",
            new_callable=AsyncMock,
            return_value="Groq response",
        ) as mock_groq,
    ):
        text, provider = await gateway.generate(prompt="Test circuit breaker", purpose="routing")

        assert text == "Groq response"
        assert provider == "groq"
        # Gemini was bypassed completely because circuit was OPEN!
        mock_gemini.assert_not_called()
        mock_groq.assert_called_once()


@pytest.mark.asyncio
async def test_gateway_purpose_convenience_methods():
    """Verify purpose-tagged helper methods dispatch correctly."""
    settings = Settings(
        GEMINI_API_KEY="test_key",
        PROVIDER_PRIORITY=["gemini"],
    )
    gateway = ModelGateway(settings=settings)

    with patch.object(gateway.providers["gemini"], "generate_text", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = "DECISION: relevant"
        grade_res, _ = await gateway.grade(prompt="Chunk text")
        assert grade_res == "DECISION: relevant"

        mock_gemini.return_value = "ROUTE: retrieve"
        route_res, _ = await gateway.route(prompt="User query")
        assert route_res == "ROUTE: retrieve"

        mock_gemini.return_value = "STATUS: SUPPORTED\nSCORE: 0.9"
        ground_res, _ = await gateway.check_groundedness(prompt="Draft text")
        assert "SUPPORTED" in ground_res

        mock_gemini.return_value = "Rewritten query string"
        rewrite_res, _ = await gateway.rewrite_query(prompt="Query text")
        assert rewrite_res == "Rewritten query string"

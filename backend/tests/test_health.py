"""Tests for the health endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok_when_db_available(client: AsyncClient) -> None:
    """Health endpoint reports ok when the database responds."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.execute = AsyncMock()

    with patch("app.api.v1.endpoints.health.AsyncSessionLocal", return_value=mock_session):
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert payload["app_name"] == "LegalLink"
    assert "version" in payload
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_health_returns_degraded_when_db_unavailable(client: AsyncClient) -> None:
    """Health endpoint reports degraded when the database is unreachable."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.execute = AsyncMock(side_effect=ConnectionError("db down"))

    with patch("app.api.v1.endpoints.health.AsyncSessionLocal", return_value=mock_session):
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"] == "unavailable"

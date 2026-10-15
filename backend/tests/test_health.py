import pytest
from httpx import AsyncClient
from app.core.config import Settings
from app.core.database import check_database_connection


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Social Operations Hub V2 API"
    assert data["status"] == "running"
    assert "docs_url" in data


@pytest.mark.asyncio
async def test_health_connected_deterministic(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """
    Deterministic test: when database connection succeeds,
    status code must be 200, status must be 'healthy', and error must be None.
    """
    async def mock_check_db():
        return True, 1.25, None

    monkeypatch.setattr("app.api.health.check_database_connection", mock_check_db)

    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["api"] == "ok"
    assert data["database"] == "connected"
    assert data["database_latency_ms"] == 1.25
    assert data["error"] is None
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_unavailable_deterministic(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """
    Deterministic test: when database connection fails,
    status code must be 503, status must be 'degraded',
    and raw database internal exceptions must NOT be exposed in the response.
    """
    sensitive_db_error = "asyncpg.exceptions.ConnectionDoesNotExistError: connection to 'postgres:5432' failed password auth"

    async def mock_check_db():
        return False, 12.34, sensitive_db_error

    monkeypatch.setattr("app.api.health.check_database_connection", mock_check_db)

    response = await async_client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["api"] == "ok"
    assert data["database"] == "unreachable"
    assert data["database_latency_ms"] == 12.34
    assert data["error"] == "Database connection unavailable"
    # Ensure sensitive raw error details are never leaked in public response
    assert sensitive_db_error not in response.text
    assert "password auth" not in response.text


@pytest.mark.asyncio
async def test_cors_headers_allowed_origin(async_client: AsyncClient):
    """
    Ensures allowed CORS origins receive appropriate Access-Control headers with credentials.
    """
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    }
    response = await async_client.get("/health", headers=headers)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_unallowed_origin(async_client: AsyncClient):
    """
    Ensures unallowed origins do not receive permissive Access-Control-Allow-Origin header.
    """
    headers = {
        "Origin": "http://untrusted-site.com",
    }
    response = await async_client.get("/health", headers=headers)
    assert response.headers.get("access-control-allow-origin") != "http://untrusted-site.com"


def test_cors_origins_config_parsing():
    """
    Tests that Settings correctly parses comma-separated strings, JSON arrays, and lists.
    """
    s1 = Settings(CORS_ORIGINS="http://localhost:3000,http://example.com")
    assert s1.CORS_ORIGINS == ["http://localhost:3000", "http://example.com"]

    s2 = Settings(CORS_ORIGINS='["http://localhost:3000", "http://example.com"]')
    assert s2.CORS_ORIGINS == ["http://localhost:3000", "http://example.com"]

    s3 = Settings(CORS_ORIGINS=["http://localhost:3000"])
    assert s3.CORS_ORIGINS == ["http://localhost:3000"]


@pytest.mark.asyncio
async def test_check_database_connection_failure_handling(monkeypatch: pytest.MonkeyPatch):
    """
    Tests that check_database_connection safely catches exceptions and returns formatted tuple.
    """
    import app.core.database as db_mod

    class FailingEngine:
        def connect(self):
            raise Exception("Simulated socket error")

    monkeypatch.setattr(db_mod, "engine", FailingEngine())

    connected, latency_ms, error = await db_mod.check_database_connection()
    assert connected is False
    assert isinstance(latency_ms, float)
    assert "Simulated socket error" in error

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import verify_password
from app.models.user import User, WorkspaceMember
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient, db_session: AsyncSession):
    payload = {
        "email": "sarah.connor@example.com",
        "password": "SuperSecretPassword123!",
        "full_name": "Sarah Connor",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "sarah.connor@example.com"
    assert data["user"]["full_name"] == "Sarah Connor"
    assert data["user"]["is_active"] is True

    # Verify user in database has hashed password, not plaintext
    stmt = select(User).where(User.email == "sarah.connor@example.com")
    res = await db_session.execute(stmt)
    user = res.scalar_one()
    assert user.hashed_password != payload["password"]
    assert verify_password(payload["password"], user.hashed_password) is True

    # Verify default workspace was created and user is owner
    ws_member_stmt = select(WorkspaceMember).where(WorkspaceMember.user_id == user.id)
    ws_member_res = await db_session.execute(ws_member_stmt)
    membership = ws_member_res.scalar_one()
    assert membership.role == "owner"


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(async_client: AsyncClient, test_user_factory):
    await test_user_factory(email="existing@example.com", password="Password123")

    payload = {
        "email": "EXISTING@example.com",  # test case-insensitive duplicate check
        "password": "AnotherPassword456",
        "full_name": "Duplicate Tester",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_short_password_validation(async_client: AsyncClient):
    payload = {
        "email": "shortpass@example.com",
        "password": "short",
        "full_name": "Short Password",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="login_user@example.com", password="ValidPassword123!")

    payload = {
        "email": "login_user@example.com",
        "password": "ValidPassword123!",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "login_user@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password_fails(async_client: AsyncClient, test_user_factory):
    await test_user_factory(email="wrongpass@example.com", password="ValidPassword123!")

    payload = {
        "email": "wrongpass@example.com",
        "password": "IncorrectPassword999!",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user_fails(async_client: AsyncClient):
    payload = {
        "email": "nobody@example.com",
        "password": "Password123!",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_inactive_user_fails(async_client: AsyncClient, test_user_factory, db_session: AsyncSession):
    setup = await test_user_factory(email="inactive@example.com", password="Password123!")
    user = setup["user"]
    user.is_active = False
    await db_session.commit()

    payload = {
        "email": "inactive@example.com",
        "password": "Password123!",
    }
    response = await async_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 400
    assert "Inactive user account" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_current_user_me_endpoint(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="profile@example.com", full_name="Profile Owner")

    # Authenticated call
    response = await async_client.get("/api/v1/auth/me", headers=setup["headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile@example.com"
    assert data["full_name"] == "Profile Owner"

    # Unauthenticated call
    unauth_resp = await async_client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == 401

    # Malformed token call
    bad_resp = await async_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-token"})
    assert bad_resp.status_code == 401

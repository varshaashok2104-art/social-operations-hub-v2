import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_create_workspace(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="owner1@example.com")
    headers = setup["headers"]

    payload = {
        "name": "Acme Marketing",
        "description": "Acme Social Operations Team",
    }
    response = await async_client.post("/api/v1/workspaces", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Marketing"
    assert data["slug"].startswith("acme-marketing")
    assert data["role"] == "owner"


@pytest.mark.asyncio
async def test_create_workspace_duplicate_slug_auto_suffix(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="owner_slug@example.com")
    headers = setup["headers"]

    payload1 = {"name": "Duplicate Team", "slug": "dup-team"}
    res1 = await async_client.post("/api/v1/workspaces", json=payload1, headers=headers)
    assert res1.status_code == 201
    assert res1.json()["slug"] == "dup-team"

    payload2 = {"name": "Duplicate Team", "slug": "dup-team"}
    res2 = await async_client.post("/api/v1/workspaces", json=payload2, headers=headers)
    assert res2.status_code == 201
    assert res2.json()["slug"].startswith("dup-team-")


@pytest.mark.asyncio
async def test_list_workspaces_tenant_isolation(async_client: AsyncClient, test_user_factory):
    user_a = await test_user_factory(email="usera@example.com", full_name="User A")
    user_b = await test_user_factory(email="userb@example.com", full_name="User B")

    # User A listing
    res_a = await async_client.get("/api/v1/workspaces", headers=user_a["headers"])
    assert res_a.status_code == 200
    workspaces_a = res_a.json()
    assert len(workspaces_a) == 1
    assert workspaces_a[0]["id"] == str(user_a["workspace"].id)

    # User B listing
    res_b = await async_client.get("/api/v1/workspaces", headers=user_b["headers"])
    assert res_b.status_code == 200
    workspaces_b = res_b.json()
    assert len(workspaces_b) == 1
    assert workspaces_b[0]["id"] == str(user_b["workspace"].id)


@pytest.mark.asyncio
async def test_get_workspace_forbidden_for_non_member(async_client: AsyncClient, test_user_factory):
    user_a = await test_user_factory(email="usera_detail@example.com")
    user_b = await test_user_factory(email="userb_detail@example.com")

    # User B trying to access User A's workspace
    ws_a_id = user_a["workspace"].id
    res = await async_client.get(f"/api/v1/workspaces/{ws_a_id}", headers=user_b["headers"])
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_and_delete_workspace(async_client: AsyncClient, test_user_factory, db_session: AsyncSession):
    user = await test_user_factory(email="ws_updater@example.com")
    ws_id = user["workspace"].id

    # Update
    update_res = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}",
        json={"name": "Renamed Workspace", "description": "New Desc"},
        headers=user["headers"],
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Renamed Workspace"

    # Delete
    del_res = await async_client.delete(f"/api/v1/workspaces/{ws_id}", headers=user["headers"])
    assert del_res.status_code == 204

    # Verify deleted in db
    check_stmt = select(Workspace).where(Workspace.id == ws_id)
    check_res = await db_session.execute(check_stmt)
    assert check_res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_workspace_members_workflow(async_client: AsyncClient, test_user_factory):
    owner = await test_user_factory(email="ws_owner@example.com", full_name="Workspace Owner")
    colleague = await test_user_factory(email="colleague@example.com", full_name="Colleague Member")
    ws_id = owner["workspace"].id

    # List members initially
    members_res = await async_client.get(f"/api/v1/workspaces/{ws_id}/members", headers=owner["headers"])
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 1
    assert members[0]["email"] == "ws_owner@example.com"
    assert members[0]["role"] == "owner"

    # Add colleague as member
    add_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/members",
        json={"email": "colleague@example.com", "role": "editor"},
        headers=owner["headers"],
    )
    assert add_res.status_code == 201
    add_data = add_res.json()
    assert add_data["email"] == "colleague@example.com"
    assert add_data["role"] == "editor"

    # Verify colleague can now view the workspace
    colleague_view = await async_client.get(f"/api/v1/workspaces/{ws_id}", headers=colleague["headers"])
    assert colleague_view.status_code == 200
    assert colleague_view.json()["role"] == "editor"

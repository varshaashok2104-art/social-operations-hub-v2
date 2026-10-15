from datetime import datetime, timedelta, timezone
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import PostStatus, PostTargetStatus, SocialPlatform
from app.models.post import Post, PostTarget


@pytest.mark.asyncio
async def test_create_draft_post(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="poster_draft@example.com")
    ws_id = setup["workspace"].id

    payload = {
        "content": "Exciting news! We are launching Social Ops Hub V2 today.",
        "target_platforms": ["x", "linkedin"],
        "custom_contents": {
            "x": "Exciting news! Launching today! 🚀",
        },
        "media_urls": ["https://assets.example.com/promo.png"],
    }
    response = await async_client.post(f"/api/v1/workspaces/{ws_id}/posts", json=payload, headers=setup["headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == payload["content"]
    assert data["status"] == "draft"
    assert data["scheduled_at"] is None
    assert len(data["targets"]) == 2

    # Check target details
    x_target = next(t for t in data["targets"] if t["platform"] == "x")
    linkedin_target = next(t for t in data["targets"] if t["platform"] == "linkedin")
    assert x_target["custom_content"] == "Exciting news! Launching today! 🚀"
    assert x_target["status"] == "draft"
    assert linkedin_target["custom_content"] is None
    assert linkedin_target["status"] == "draft"


@pytest.mark.asyncio
async def test_create_scheduled_post(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="poster_sched@example.com")
    ws_id = setup["workspace"].id
    sched_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    payload = {
        "content": "Upcoming webinar tomorrow!",
        "target_platforms": ["instagram", "facebook"],
        "scheduled_at": sched_time,
    }
    response = await async_client.post(f"/api/v1/workspaces/{ws_id}/posts", json=payload, headers=setup["headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "scheduled"
    assert data["scheduled_at"] is not None
    for t in data["targets"]:
        assert t["status"] == "scheduled"
        assert t["scheduled_at"] is not None


@pytest.mark.asyncio
async def test_create_post_validation_errors(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="poster_err@example.com")
    ws_id = setup["workspace"].id

    # Empty target platforms
    res_empty = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Hello", "target_platforms": []},
        headers=setup["headers"],
    )
    assert res_empty.status_code == 422

    # Duplicate target platforms
    res_dup = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Hello", "target_platforms": ["x", "x"]},
        headers=setup["headers"],
    )
    assert res_dup.status_code == 422


@pytest.mark.asyncio
async def test_list_and_search_posts(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="poster_list@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    # Create 3 posts: 1 draft, 1 scheduled, 1 with specific keyword
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Alpha release announcements", "target_platforms": ["x"]},
        headers=headers,
    )
    sched_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Beta release coming up", "target_platforms": ["linkedin"], "scheduled_at": sched_time},
        headers=headers,
    )
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Gamma patch released", "target_platforms": ["facebook"]},
        headers=headers,
    )

    # List all
    all_res = await async_client.get(f"/api/v1/workspaces/{ws_id}/posts", headers=headers)
    assert all_res.status_code == 200
    assert len(all_res.json()) == 3

    # Filter by status = scheduled
    sched_res = await async_client.get(f"/api/v1/workspaces/{ws_id}/posts?status=scheduled", headers=headers)
    assert sched_res.status_code == 200
    assert len(sched_res.json()) == 1
    assert sched_res.json()[0]["content"] == "Beta release coming up"

    # Filter by platform = facebook
    fb_res = await async_client.get(f"/api/v1/workspaces/{ws_id}/posts?platform=facebook", headers=headers)
    assert fb_res.status_code == 200
    assert len(fb_res.json()) == 1
    assert fb_res.json()[0]["content"] == "Gamma patch released"

    # Search keyword
    search_res = await async_client.get(f"/api/v1/workspaces/{ws_id}/posts?search=Alpha", headers=headers)
    assert search_res.status_code == 200
    assert len(search_res.json()) == 1
    assert search_res.json()[0]["content"] == "Alpha release announcements"


@pytest.mark.asyncio
async def test_posts_tenant_isolation(async_client: AsyncClient, test_user_factory):
    user_a = await test_user_factory(email="tenant_a@example.com")
    user_b = await test_user_factory(email="tenant_b@example.com")

    # User A creates a post
    create_res = await async_client.post(
        f"/api/v1/workspaces/{user_a['workspace'].id}/posts",
        json={"content": "Secret Project Launch", "target_platforms": ["x"]},
        headers=user_a["headers"],
    )
    post_a_id = create_res.json()["id"]

    # User B lists posts in User B's workspace -> must be empty
    list_b = await async_client.get(
        f"/api/v1/workspaces/{user_b['workspace'].id}/posts",
        headers=user_b["headers"],
    )
    assert len(list_b.json()) == 0

    # User B attempts to access User A's post directly -> 403 Forbidden
    detail_b = await async_client.get(
        f"/api/v1/workspaces/{user_a['workspace'].id}/posts/{post_a_id}",
        headers=user_b["headers"],
    )
    assert detail_b.status_code == 403


@pytest.mark.asyncio
async def test_update_and_delete_post(async_client: AsyncClient, test_user_factory, db_session: AsyncSession):
    setup = await test_user_factory(email="poster_update@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    create_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Original Content", "target_platforms": ["x"]},
        headers=headers,
    )
    post_id = create_res.json()["id"]

    # Update content and media
    update_res = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}",
        json={"content": "Updated Content", "media_urls": ["https://cdn.example.com/asset.png"]},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["content"] == "Updated Content"
    assert update_res.json()["media_urls"] == ["https://cdn.example.com/asset.png"]

    # Delete post
    del_res = await async_client.delete(f"/api/v1/workspaces/{ws_id}/posts/{post_id}", headers=headers)
    assert del_res.status_code == 204

    # Verify deleted in db
    check_stmt = select(Post).where(Post.id == uuid.UUID(post_id))
    res = await db_session.execute(check_stmt)
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_post_targets_lifecycle(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="poster_targets@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    # Create post with X
    create_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Multi-platform rollout", "target_platforms": ["x"]},
        headers=headers,
    )
    post_id = create_res.json()["id"]

    # 1. Update X target's custom content
    patch_target_res = await async_client.patch(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/targets/x",
        json={"custom_content": "Short tweet override"},
        headers=headers,
    )
    assert patch_target_res.status_code == 200
    x_target = next(t for t in patch_target_res.json()["targets"] if t["platform"] == "x")
    assert x_target["custom_content"] == "Short tweet override"

    # 2. Add LinkedIn as second target
    add_target_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/targets",
        json={"platform": "linkedin", "custom_content": "Professional update"},
        headers=headers,
    )
    assert add_target_res.status_code == 201
    assert len(add_target_res.json()["targets"]) == 2

    # 3. Adding duplicate target platform rejected
    dup_target_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/targets",
        json={"platform": "linkedin"},
        headers=headers,
    )
    assert dup_target_res.status_code == 400

    # 4. Remove X target
    remove_target_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/targets/x",
        headers=headers,
    )
    assert remove_target_res.status_code == 200
    assert len(remove_target_res.json()["targets"]) == 1
    assert remove_target_res.json()["targets"][0]["platform"] == "linkedin"

    # 5. Removing last target rejected
    remove_last_res = await async_client.delete(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/targets/linkedin",
        headers=headers,
    )
    assert remove_last_res.status_code == 400
    assert "Cannot remove the only target platform" in remove_last_res.json()["detail"]

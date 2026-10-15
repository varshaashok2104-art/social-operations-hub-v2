from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from app.models.enums import PostStatus, PostTargetStatus, SocialPlatform


@pytest.mark.asyncio
async def test_publish_now_success(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="pub_user@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    # Create post
    create_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={
            "content": "All systems operational! 🚀",
            "target_platforms": ["x", "linkedin", "facebook"],
        },
        headers=headers,
    )
    post_id = create_res.json()["id"]

    # Publish now
    pub_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/publish",
        headers=headers,
    )
    assert pub_res.status_code == 200
    data = pub_res.json()
    assert data["status"] == "published"
    assert data["published_at"] is not None
    assert len(data["targets"]) == 3

    for target in data["targets"]:
        assert target["status"] == "published"
        assert target["simulated_platform_post_id"].startswith(f"sim_{target['platform']}_")
        assert target["execution_log"]["status_code"] == 200
        assert target["metrics"]["impressions"] > 0
        assert "likes" in target["metrics"]


@pytest.mark.asyncio
async def test_publish_character_limit_partial_publication(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="pub_limits@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    # 350-character post (exceeds X's 280-char limit, but fits within LinkedIn's 3000-char limit)
    long_content = "A" * 350
    create_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={
            "content": long_content,
            "target_platforms": ["x", "linkedin"],
        },
        headers=headers,
    )
    post_id = create_res.json()["id"]

    pub_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/publish",
        headers=headers,
    )
    assert pub_res.status_code == 200
    data = pub_res.json()
    assert data["status"] == "partially_published"

    x_target = next(t for t in data["targets"] if t["platform"] == "x")
    li_target = next(t for t in data["targets"] if t["platform"] == "linkedin")

    assert x_target["status"] == "failed"
    assert "character limit" in x_target["error_message"]
    assert li_target["status"] == "published"


@pytest.mark.asyncio
async def test_publish_force_fail_platforms(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="pub_fail@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    create_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={
            "content": "Testing forced platform outage handling",
            "target_platforms": ["x", "facebook"],
        },
        headers=headers,
    )
    post_id = create_res.json()["id"]

    # Force fail all targets
    pub_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/publish?force_fail_platforms=x&force_fail_platforms=facebook",
        headers=headers,
    )
    assert pub_res.status_code == 200
    data = pub_res.json()
    assert data["status"] == "failed"
    for t in data["targets"]:
        assert t["status"] == "failed"
        assert "Simulated provider outage" in t["error_message"]


@pytest.mark.asyncio
async def test_schedule_and_cancel_post(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="pub_sched@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    create_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Future Product Drop", "target_platforms": ["x"]},
        headers=headers,
    )
    post_id = create_res.json()["id"]

    # Schedule
    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    sched_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/schedule",
        json={"scheduled_at": future_time},
        headers=headers,
    )
    assert sched_res.status_code == 200
    assert sched_res.json()["status"] == "scheduled"
    assert sched_res.json()["scheduled_at"] is not None

    # Cancel
    cancel_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/cancel",
        headers=headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"
    for target in cancel_res.json()["targets"]:
        assert target["status"] == "cancelled"


@pytest.mark.asyncio
async def test_retry_failed_targets(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="pub_retry@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    # Create post and publish with forced failure
    create_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Retryable content message", "target_platforms": ["x"]},
        headers=headers,
    )
    post_id = create_res.json()["id"]

    pub_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/publish?force_fail_platforms=x",
        headers=headers,
    )
    assert pub_res.json()["status"] == "failed"

    # Retry without force failure -> succeeds
    retry_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{post_id}/retry",
        headers=headers,
    )
    assert retry_res.status_code == 200
    assert retry_res.json()["status"] == "published"
    assert retry_res.json()["targets"][0]["status"] == "published"

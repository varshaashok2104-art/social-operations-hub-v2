from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from app.models.enums import PostStatus


@pytest.mark.asyncio
async def test_get_queue_pipeline_and_status_counts(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="queue_test@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    # 1. Create a draft post
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Queue Draft Item", "target_platforms": ["x"]},
        headers=headers,
    )

    # 2. Create a scheduled post
    future_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Queue Scheduled Item", "target_platforms": ["linkedin"], "scheduled_at": future_time},
        headers=headers,
    )

    # 3. Create and publish a post
    pub_create = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Queue Published Item", "target_platforms": ["facebook"]},
        headers=headers,
    )
    post_pub_id = pub_create.json()["id"]
    await async_client.post(f"/api/v1/workspaces/{ws_id}/posts/{post_pub_id}/publish", headers=headers)

    # Get queue
    res = await async_client.get(f"/api/v1/workspaces/{ws_id}/queue", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["counts_by_status"]["draft"] == 1
    assert data["counts_by_status"]["scheduled"] == 1
    assert data["counts_by_status"]["published"] == 1

    # Filter queue by status = scheduled
    sched_filter = await async_client.get(f"/api/v1/workspaces/{ws_id}/queue?status=scheduled", headers=headers)
    assert sched_filter.status_code == 200
    assert sched_filter.json()["total"] == 1
    assert sched_filter.json()["items"][0]["content"] == "Queue Scheduled Item"


@pytest.mark.asyncio
async def test_publish_due_queue_processing(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="queue_due@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    now = datetime.now(timezone.utc)
    past_due_time = (now - timedelta(minutes=15)).isoformat()
    future_time = (now + timedelta(days=2)).isoformat()

    # Post 1: Past due post (should be processed)
    due_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Due for immediate release", "target_platforms": ["x"], "scheduled_at": past_due_time},
        headers=headers,
    )
    due_post_id = due_res.json()["id"]

    # Post 2: Future scheduled post (should NOT be processed)
    future_res = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Future drop", "target_platforms": ["linkedin"], "scheduled_at": future_time},
        headers=headers,
    )
    future_post_id = future_res.json()["id"]

    # Trigger publish-due endpoint
    process_res = await async_client.post(f"/api/v1/workspaces/{ws_id}/queue/publish-due", headers=headers)
    assert process_res.status_code == 200
    proc_data = process_res.json()
    assert proc_data["processed_count"] == 1
    assert proc_data["published_count"] == 1
    assert proc_data["failed_count"] == 0
    assert due_post_id in [str(p_id) for p_id in proc_data["post_ids"]]

    # Verify Post 1 is now published
    p1 = await async_client.get(f"/api/v1/workspaces/{ws_id}/posts/{due_post_id}", headers=headers)
    assert p1.json()["status"] == "published"

    # Verify Post 2 is still scheduled
    p2 = await async_client.get(f"/api/v1/workspaces/{ws_id}/posts/{future_post_id}", headers=headers)
    assert p2.json()["status"] == "scheduled"

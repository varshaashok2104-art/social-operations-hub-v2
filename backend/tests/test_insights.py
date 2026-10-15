import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_insights_empty_workspace(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="ins_empty@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    res = await async_client.get(f"/api/v1/workspaces/{ws_id}/insights", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_posts"] == 0
    assert data["total_targets"] == 0
    assert data["publishing_velocity_posts_per_day"] == 0.0
    assert data["success_rate_percentage"] == 100.0
    assert data["total_impressions"] == 0
    assert data["total_engagements"] == 0


@pytest.mark.asyncio
async def test_insights_kpi_calculations_and_aggregation(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="ins_calc@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    # 1. Create Post 1 with X and LinkedIn, then publish (succeeds)
    p1 = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Post 1 Announcement", "target_platforms": ["x", "linkedin"]},
        headers=headers,
    )
    p1_id = p1.json()["id"]
    await async_client.post(f"/api/v1/workspaces/{ws_id}/posts/{p1_id}/publish", headers=headers)

    # 2. Create Post 2 with X and Facebook, publish with forced failure on X (partial success)
    p2 = await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Post 2 Update", "target_platforms": ["x", "facebook"]},
        headers=headers,
    )
    p2_id = p2.json()["id"]
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts/{p2_id}/publish?force_fail_platforms=x",
        headers=headers,
    )

    # 3. Create Post 3 as draft
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Post 3 Draft", "target_platforms": ["instagram"]},
        headers=headers,
    )

    # Query insights
    res = await async_client.get(f"/api/v1/workspaces/{ws_id}/insights", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_posts"] == 3
    assert data["total_targets"] == 5

    # Status distribution
    assert data["status_distribution"]["published"] == 1
    assert data["status_distribution"]["partially_published"] == 1
    assert data["status_distribution"]["draft"] == 1

    # Platform distribution (2 X, 1 LinkedIn, 1 Facebook, 1 Instagram)
    assert data["platform_distribution"]["x"] == 2
    assert data["platform_distribution"]["linkedin"] == 1
    assert data["platform_distribution"]["facebook"] == 1
    assert data["platform_distribution"]["instagram"] == 1

    # Targets attempted: 4 targets attempted (Post 1 has 2, Post 2 has 2), 3 published, 1 failed
    # Success rate: 3 / 4 = 75.0%
    assert data["success_rate_percentage"] == 75.0

    # Total impressions and engagements > 0 from simulated publishing
    assert data["total_impressions"] > 0
    assert data["total_engagements"] > 0

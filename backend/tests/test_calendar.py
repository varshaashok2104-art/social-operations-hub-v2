from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_calendar_schedule_query_window(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="cal_user@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    now = datetime.now(timezone.utc)
    t1 = (now + timedelta(days=2)).isoformat()
    t2 = (now + timedelta(days=5)).isoformat()
    t_outside = (now + timedelta(days=20)).isoformat()

    # Post 1 (inside window)
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Event A", "target_platforms": ["x", "linkedin"], "scheduled_at": t1, "media_urls": ["url1"]},
        headers=headers,
    )

    # Post 2 (inside window)
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Event B", "target_platforms": ["instagram"], "scheduled_at": t2},
        headers=headers,
    )

    # Post 3 (outside window)
    await async_client.post(
        f"/api/v1/workspaces/{ws_id}/posts",
        json={"content": "Far Future Event", "target_platforms": ["facebook"], "scheduled_at": t_outside},
        headers=headers,
    )

    # Query calendar window: now to +7 days
    start_q = now.isoformat()
    end_q = (now + timedelta(days=7)).isoformat()
    res = await async_client.get(
        f"/api/v1/workspaces/{ws_id}/calendar",
        params={"start_date": start_q, "end_date": end_q},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_posts"] == 2
    contents = [p["content"] for p in data["posts"]]
    assert "Event A" in contents
    assert "Event B" in contents
    assert "Far Future Event" not in contents

    # Check structure
    event_a = next(p for p in data["posts"] if p["content"] == "Event A")
    assert "x" in event_a["platforms"]
    assert "linkedin" in event_a["platforms"]
    assert event_a["media_count"] == 1


@pytest.mark.asyncio
async def test_calendar_invalid_date_window(async_client: AsyncClient, test_user_factory):
    setup = await test_user_factory(email="cal_err@example.com")
    ws_id = setup["workspace"].id
    headers = setup["headers"]

    now = datetime.now(timezone.utc)
    start_q = (now + timedelta(days=5)).isoformat()
    end_q = now.isoformat()

    res = await async_client.get(
        f"/api/v1/workspaces/{ws_id}/calendar",
        params={"start_date": start_q, "end_date": end_q},
        headers=headers,
    )
    assert res.status_code == 400
    assert "cannot be greater than" in res.json()["detail"]

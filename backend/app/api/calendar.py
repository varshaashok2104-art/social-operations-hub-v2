from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_workspace_membership
from app.core.database import get_db_session
from app.models.post import Post
from app.models.user import WorkspaceMember
from app.schemas.calendar import CalendarPostItem, CalendarResponse

router = APIRouter(prefix="/workspaces/{workspace_id}/calendar", tags=["Calendar"])


@router.get("", response_model=CalendarResponse)
async def get_calendar_posts(
    workspace_id: uuid.UUID,
    start_date: datetime = Query(..., description="Start of date range (ISO 8601)"),
    end_date: datetime = Query(..., description="End of date range (ISO 8601)"),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be greater than end_date",
        )

    stmt = (
        select(Post)
        .options(selectinload(Post.targets))
        .where(
            Post.workspace_id == workspace_id,
            or_(
                Post.scheduled_at.between(start_date, end_date),
                Post.published_at.between(start_date, end_date),
            ),
        )
        .order_by(Post.scheduled_at.asc().nulls_last(), Post.published_at.asc().nulls_last())
    )
    result = await db.execute(stmt)
    posts = result.scalars().all()

    items = []
    for p in posts:
        target_time = p.scheduled_at or p.published_at or p.created_at
        items.append(
            CalendarPostItem(
                id=p.id,
                content=p.content,
                status=p.status,
                scheduled_at=target_time,
                platforms=[t.platform for t in p.targets],
                media_count=len(p.media_urls),
            )
        )

    return CalendarResponse(
        start_date=start_date,
        end_date=end_date,
        total_posts=len(items),
        posts=items,
    )

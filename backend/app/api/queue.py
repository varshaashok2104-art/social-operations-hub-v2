from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_workspace_membership
from app.core.database import get_db_session
from app.models.enums import PostStatus, SocialPlatform
from app.models.post import Post, PostTarget
from app.models.user import WorkspaceMember
from app.schemas.post import PostResponse
from app.schemas.queue import QueuePublishDueResponse, QueueResponse
from app.services.publisher import sandbox_publisher

router = APIRouter(prefix="/workspaces/{workspace_id}/queue", tags=["Queue"])


@router.get("", response_model=QueueResponse)
async def get_queue(
    workspace_id: uuid.UUID,
    status_filter: PostStatus | None = Query(None, alias="status"),
    platform_filter: SocialPlatform | None = Query(None, alias="platform"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    # Calculate counts by status for all posts in this workspace
    count_stmt = (
        select(Post.status, func.count(Post.id))
        .where(Post.workspace_id == workspace_id)
        .group_by(Post.status)
    )
    count_res = await db.execute(count_stmt)
    raw_counts = {row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in count_res.all()}

    all_statuses = [
        PostStatus.DRAFT.value,
        PostStatus.SCHEDULED.value,
        PostStatus.PUBLISHING.value,
        PostStatus.PUBLISHED.value,
        PostStatus.PARTIALLY_PUBLISHED.value,
        PostStatus.FAILED.value,
        PostStatus.CANCELLED.value,
    ]
    counts_by_status = {s: raw_counts.get(s, 0) for s in all_statuses}

    # Query filtered items
    stmt = (
        select(Post)
        .options(selectinload(Post.targets))
        .where(Post.workspace_id == workspace_id)
    )
    if status_filter:
        stmt = stmt.where(Post.status == status_filter)

    if platform_filter:
        stmt = stmt.join(PostTarget, Post.id == PostTarget.post_id).where(PostTarget.platform == platform_filter)

    # Count total for the active filter
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(total_stmt)
    total = total_res.scalar() or 0

    # Fetch items with ordering: scheduled time ascending (nulls last), then created_at desc
    stmt = stmt.order_by(Post.scheduled_at.asc().nulls_last(), Post.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    posts = result.scalars().all()

    return QueueResponse(
        items=[PostResponse.model_validate(p) for p in posts],
        total=total,
        counts_by_status=counts_by_status,
    )


@router.post("/publish-due", response_model=QueuePublishDueResponse)
async def publish_due_posts(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    now = datetime.now(timezone.utc)
    stmt = (
        select(Post)
        .options(selectinload(Post.targets))
        .where(
            Post.workspace_id == workspace_id,
            Post.status == PostStatus.SCHEDULED,
            Post.scheduled_at <= now,
        )
    )
    result = await db.execute(stmt)
    due_posts = result.scalars().all()

    published_count = 0
    failed_count = 0
    processed_ids = []

    for post in due_posts:
        processed_ids.append(post.id)
        await sandbox_publisher.publish_post(post)
        if post.status in (PostStatus.PUBLISHED, PostStatus.PARTIALLY_PUBLISHED):
            published_count += 1
        else:
            failed_count += 1

    await db.commit()

    return QueuePublishDueResponse(
        processed_count=len(due_posts),
        published_count=published_count,
        failed_count=failed_count,
        post_ids=processed_ids,
    )

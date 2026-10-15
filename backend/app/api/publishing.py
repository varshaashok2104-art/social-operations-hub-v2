import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_workspace_membership
from app.core.database import get_db_session
from app.models.enums import PostStatus, PostTargetStatus, SocialPlatform
from app.models.post import Post
from app.models.user import WorkspaceMember
from app.schemas.post import PostPublishResponse, PostResponse, PostScheduleRequest, PostTargetResponse
from app.services.publisher import sandbox_publisher

router = APIRouter(prefix="/workspaces/{workspace_id}/posts/{post_id}", tags=["Publishing"])


@router.post("/publish", response_model=PostPublishResponse)
async def publish_post_now(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    force_fail_platforms: list[SocialPlatform] | None = Query(None),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(Post)
        .options(selectinload(Post.targets))
        .where(Post.id == post_id, Post.workspace_id == workspace_id)
    )
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if not post.targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish a post without target platforms",
        )

    # Execute simulation publication
    await sandbox_publisher.publish_post(post, force_fail_platforms=force_fail_platforms)
    await db.commit()
    await db.refresh(post)

    return PostPublishResponse(
        post_id=post.id,
        status=post.status,
        published_at=post.published_at,
        targets=[PostTargetResponse.model_validate(t) for t in post.targets],
    )


@router.post("/schedule", response_model=PostResponse)
async def schedule_post(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    data: PostScheduleRequest,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(Post)
        .options(selectinload(Post.targets))
        .where(Post.id == post_id, Post.workspace_id == workspace_id)
    )
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    post.scheduled_at = data.scheduled_at
    post.status = PostStatus.SCHEDULED
    for target in post.targets:
        target.scheduled_at = data.scheduled_at
        target.status = PostTargetStatus.SCHEDULED

    await db.commit()
    await db.refresh(post)
    return post


@router.post("/cancel", response_model=PostResponse)
async def cancel_post(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(Post)
        .options(selectinload(Post.targets))
        .where(Post.id == post_id, Post.workspace_id == workspace_id)
    )
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.status == PostStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel an already published post",
        )

    for target in post.targets:
        if target.status != PostTargetStatus.PUBLISHED:
            target.status = PostTargetStatus.CANCELLED

    post.sync_status()
    await db.commit()
    await db.refresh(post)
    return post


@router.post("/retry", response_model=PostPublishResponse)
async def retry_failed_targets(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(Post)
        .options(selectinload(Post.targets))
        .where(Post.id == post_id, Post.workspace_id == workspace_id)
    )
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    failed_targets = [t for t in post.targets if t.status == PostTargetStatus.FAILED]
    if not failed_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No failed targets found to retry on this post",
        )

    for target in failed_targets:
        target.status = PostTargetStatus.PUBLISHING
        await sandbox_publisher.publish_target(post, target)

    post.sync_status()
    await db.commit()
    await db.refresh(post)

    return PostPublishResponse(
        post_id=post.id,
        status=post.status,
        published_at=post.published_at,
        targets=[PostTargetResponse.model_validate(t) for t in post.targets],
    )

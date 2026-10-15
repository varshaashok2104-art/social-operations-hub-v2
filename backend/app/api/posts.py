import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.deps import get_workspace_membership
from app.core.database import get_db_session
from app.models.enums import PostStatus, PostTargetStatus, SocialPlatform
from app.models.post import Post, PostTarget
from app.models.user import WorkspaceMember
from app.schemas.post import (
    PostCreate,
    PostResponse,
    PostTargetAdd,
    PostTargetResponse,
    PostTargetUpdate,
    PostUpdate,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/posts", tags=["Posts"])


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    workspace_id: uuid.UUID,
    data: PostCreate,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    if not data.target_platforms:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one target platform must be selected",
        )

    # Check for duplicate target platforms
    unique_platforms = set(data.target_platforms)
    if len(unique_platforms) != len(data.target_platforms):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate target platforms are not allowed in a single post",
        )

    initial_post_status = PostStatus.SCHEDULED if data.scheduled_at else PostStatus.DRAFT
    initial_target_status = PostTargetStatus.SCHEDULED if data.scheduled_at else PostTargetStatus.DRAFT

    post = Post(
        workspace_id=workspace_id,
        content=data.content,
        media_urls=data.media_urls,
        status=initial_post_status,
        scheduled_at=data.scheduled_at,
    )
    db.add(post)
    await db.flush()

    custom_map = data.custom_contents or {}
    for platform in data.target_platforms:
        target = PostTarget(
            post_id=post.id,
            platform=platform,
            custom_content=custom_map.get(platform),
            status=initial_target_status,
            scheduled_at=data.scheduled_at,
        )
        db.add(target)

    await db.commit()

    # Re-fetch with targets loaded
    stmt = select(Post).options(selectinload(Post.targets)).where(Post.id == post.id)
    res = await db.execute(stmt)
    loaded_post = res.scalar_one()
    return loaded_post


@router.get("", response_model=list[PostResponse])
async def list_posts(
    workspace_id: uuid.UUID,
    status_filter: PostStatus | None = Query(None, alias="status"),
    platform_filter: SocialPlatform | None = Query(None, alias="platform"),
    search: str | None = Query(None, description="Search post content"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(Post)
        .options(selectinload(Post.targets))
        .where(Post.workspace_id == workspace_id)
    )

    if status_filter:
        stmt = stmt.where(Post.status == status_filter)

    if search:
        stmt = stmt.where(Post.content.ilike(f"%{search.strip()}%"))

    if platform_filter:
        stmt = stmt.join(PostTarget, Post.id == PostTarget.post_id).where(PostTarget.platform == platform_filter)

    stmt = stmt.order_by(Post.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    posts = result.scalars().all()
    return posts


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
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
    return post


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    data: PostUpdate,
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

    if data.content is not None:
        post.content = data.content
    if data.media_urls is not None:
        post.media_urls = data.media_urls
    if data.scheduled_at is not None:
        post.scheduled_at = data.scheduled_at
        if post.status == PostStatus.DRAFT:
            post.status = PostStatus.SCHEDULED
        for t in post.targets:
            t.scheduled_at = data.scheduled_at
            if t.status == PostTargetStatus.DRAFT:
                t.status = PostTargetStatus.SCHEDULED

    await db.commit()
    await db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Post).where(Post.id == post_id, Post.workspace_id == workspace_id)
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    await db.delete(post)
    await db.commit()
    return None


@router.patch("/{post_id}/targets/{platform}", response_model=PostResponse)
async def update_post_target(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    platform: SocialPlatform,
    data: PostTargetUpdate,
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

    target = next((t for t in post.targets if t.platform == platform), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target for {platform.value} not found on this post",
        )

    if data.custom_content is not None:
        target.custom_content = data.custom_content

    await db.commit()
    await db.refresh(post)
    return post


@router.post("/{post_id}/targets", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def add_post_target(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    data: PostTargetAdd,
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

    if any(t.platform == data.platform for t in post.targets):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target for platform {data.platform.value} already exists on this post",
        )

    target_status = PostTargetStatus.SCHEDULED if post.scheduled_at else PostTargetStatus.DRAFT
    new_target = PostTarget(
        post_id=post.id,
        platform=data.platform,
        custom_content=data.custom_content,
        status=target_status,
        scheduled_at=post.scheduled_at,
    )
    db.add(new_target)
    post.targets.append(new_target)
    post.sync_status()

    await db.commit()
    await db.refresh(post)
    return post


@router.delete("/{post_id}/targets/{platform}", response_model=PostResponse)
async def remove_post_target(
    workspace_id: uuid.UUID,
    post_id: uuid.UUID,
    platform: SocialPlatform,
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

    if len(post.targets) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the only target platform from a post",
        )

    target = next((t for t in post.targets if t.platform == platform), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target for {platform.value} not found on this post",
        )

    await db.delete(target)
    post.targets = [t for t in post.targets if t.id != target.id]
    post.sync_status()

    await db.commit()
    await db.refresh(post)
    return post

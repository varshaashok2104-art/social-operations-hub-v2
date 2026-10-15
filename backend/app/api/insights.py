from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_workspace_membership
from app.core.database import get_db_session
from app.models.enums import PostStatus, PostTargetStatus, SocialPlatform
from app.models.post import Post, PostTarget
from app.models.user import WorkspaceMember
from app.schemas.insights import InsightsSummary

router = APIRouter(prefix="/workspaces/{workspace_id}/insights", tags=["Insights"])


@router.get("", response_model=InsightsSummary)
async def get_insights_summary(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    # Total posts
    post_count_stmt = select(func.count(Post.id)).where(Post.workspace_id == workspace_id)
    post_count_res = await db.execute(post_count_stmt)
    total_posts = post_count_res.scalar() or 0

    # Total targets & platform distribution
    target_dist_stmt = (
        select(PostTarget.platform, func.count(PostTarget.id))
        .join(Post, PostTarget.post_id == Post.id)
        .where(Post.workspace_id == workspace_id)
        .group_by(PostTarget.platform)
    )
    target_dist_res = await db.execute(target_dist_stmt)
    raw_platform_dist = {row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in target_dist_res.all()}
    total_targets = sum(raw_platform_dist.values())
    platform_distribution = {
        p.value: raw_platform_dist.get(p.value, 0)
        for p in (SocialPlatform.X, SocialPlatform.LINKEDIN, SocialPlatform.INSTAGRAM, SocialPlatform.FACEBOOK)
    }

    # Status distribution
    status_stmt = (
        select(Post.status, func.count(Post.id))
        .where(Post.workspace_id == workspace_id)
        .group_by(Post.status)
    )
    status_res = await db.execute(status_stmt)
    raw_status_dist = {row[0].value if hasattr(row[0], "value") else str(row[0]): row[1] for row in status_res.all()}
    all_statuses = [
        PostStatus.DRAFT.value,
        PostStatus.SCHEDULED.value,
        PostStatus.PUBLISHING.value,
        PostStatus.PUBLISHED.value,
        PostStatus.PARTIALLY_PUBLISHED.value,
        PostStatus.FAILED.value,
        PostStatus.CANCELLED.value,
    ]
    status_distribution = {s: raw_status_dist.get(s, 0) for s in all_statuses}

    # Velocity: posts published in the last 30 days
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    velocity_stmt = select(func.count(Post.id)).where(
        Post.workspace_id == workspace_id,
        Post.status.in_([PostStatus.PUBLISHED, PostStatus.PARTIALLY_PUBLISHED]),
        Post.published_at >= thirty_days_ago,
    )
    velocity_res = await db.execute(velocity_stmt)
    recent_published = velocity_res.scalar() or 0
    publishing_velocity = round(recent_published / 30.0, 2)

    # Success rate & metrics aggregation across all targets
    targets_stmt = (
        select(PostTarget.status, PostTarget.metrics)
        .join(Post, PostTarget.post_id == Post.id)
        .where(Post.workspace_id == workspace_id)
    )
    targets_res = await db.execute(targets_stmt)
    targets_rows = targets_res.all()

    published_targets_count = 0
    failed_targets_count = 0
    total_impressions = 0
    total_engagements = 0

    for t_status, metrics in targets_rows:
        status_val = t_status.value if hasattr(t_status, "value") else str(t_status)
        if status_val == PostTargetStatus.PUBLISHED.value:
            published_targets_count += 1
            if isinstance(metrics, dict):
                total_impressions += int(metrics.get("impressions", 0))
                likes = int(metrics.get("likes", 0))
                clicks = int(metrics.get("clicks", 0))
                shares = int(metrics.get("shares", 0))
                total_engagements += (likes + clicks + shares)
        elif status_val == PostTargetStatus.FAILED.value:
            failed_targets_count += 1

    total_attempted = published_targets_count + failed_targets_count
    if total_attempted > 0:
        success_rate = round((published_targets_count / total_attempted) * 100.0, 1)
    else:
        success_rate = 100.0

    return InsightsSummary(
        total_posts=total_posts,
        total_targets=total_targets,
        status_distribution=status_distribution,
        platform_distribution=platform_distribution,
        publishing_velocity_posts_per_day=publishing_velocity,
        success_rate_percentage=success_rate,
        total_impressions=total_impressions,
        total_engagements=total_engagements,
    )

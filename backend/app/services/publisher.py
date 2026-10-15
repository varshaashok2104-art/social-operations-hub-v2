import asyncio
from datetime import datetime, timezone
import random
import time
import uuid
from app.core.config import settings
from app.models.enums import PostStatus, PostTargetStatus, SocialPlatform
from app.models.post import Post, PostTarget


PLATFORM_CHARACTER_LIMITS = {
    SocialPlatform.X: 280,
    SocialPlatform.LINKEDIN: 3000,
    SocialPlatform.INSTAGRAM: 2200,
    SocialPlatform.FACEBOOK: 5000,
}


class SandboxSocialPublisher:
    """
    Simulated publisher adapter for social networks.
    Enforces network-specific constraints, simulates delivery latency and error outcomes,
    and returns simulated platform identifiers and metrics without requiring live credentials.
    """

    def __init__(self, latency_ms: int | None = None):
        self.latency_ms = latency_ms if latency_ms is not None else settings.SIMULATED_NETWORK_LATENCY_MS

    async def publish_target(self, post: Post, target: PostTarget, force_fail: bool = False) -> bool:
        start_time = time.perf_counter()
        now = datetime.now(timezone.utc)

        # Simulate async network latency if configured
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        # Determine effective content (custom platform override or master post content)
        effective_content = target.custom_content if target.custom_content is not None else post.content
        char_limit = PLATFORM_CHARACTER_LIMITS.get(target.platform, 5000)

        # Validate platform rules
        if force_fail:
            error_msg = f"Simulated provider outage on {target.platform.value}"
            success = False
        elif len(effective_content) > char_limit:
            error_msg = f"Content exceeds {target.platform.value} character limit ({len(effective_content)} > {char_limit})"
            success = False
        elif target.platform == SocialPlatform.INSTAGRAM and not effective_content.strip() and not post.media_urls:
            error_msg = "Instagram requires either caption text or at least one media asset"
            success = False
        else:
            error_msg = None
            success = True

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if success:
            sim_id = f"sim_{target.platform.value}_{uuid.uuid4().hex[:12]}"
            # Generate deterministic/pseudo-random simulated engagement metrics
            seed = int(uuid.uuid4().hex[:8], 16)
            impressions = 80 + (seed % 350)
            likes = 3 + (seed % 35)
            clicks = 1 + (seed % 20)
            shares = seed % 12

            target.status = PostTargetStatus.PUBLISHED
            target.published_at = now
            target.simulated_platform_post_id = sim_id
            target.error_message = None
            target.execution_log = {
                "latency_ms": elapsed_ms,
                "status_code": 200,
                "simulated_at": now.isoformat(),
                "adapter": "SandboxSocialPublisher",
            }
            target.metrics = {
                "impressions": impressions,
                "likes": likes,
                "clicks": clicks,
                "shares": shares,
            }
        else:
            target.status = PostTargetStatus.FAILED
            target.error_message = error_msg
            target.execution_log = {
                "latency_ms": elapsed_ms,
                "status_code": 400,
                "simulated_at": now.isoformat(),
                "error": error_msg,
                "adapter": "SandboxSocialPublisher",
            }

        return success

    async def publish_post(self, post: Post, force_fail_platforms: list[SocialPlatform] | None = None) -> Post:
        """
        Publishes a post across all its targets using the sandbox publisher,
        then synchronizes the aggregate post status.
        """
        now = datetime.now(timezone.utc)
        post.status = PostStatus.PUBLISHING

        force_fail_list = force_fail_platforms or []
        for target in post.targets:
            target.status = PostTargetStatus.PUBLISHING
            force_fail = target.platform in force_fail_list
            await self.publish_target(post, target, force_fail=force_fail)

        # Synchronize aggregate parent status
        post.sync_status()
        if post.status in (PostStatus.PUBLISHED, PostStatus.PARTIALLY_PUBLISHED):
            post.published_at = now

        return post


sandbox_publisher = SandboxSocialPublisher()

from enum import StrEnum
from typing import Sequence


class SocialPlatform(StrEnum):
    X = "x"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class PostStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PARTIALLY_PUBLISHED = "partially_published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PostTargetStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


def compute_aggregate_post_status(target_statuses: Sequence[PostTargetStatus | str]) -> PostStatus:
    """
    Pure, deterministic helper to compute aggregate PostStatus from its child PostTarget states.

    Precedence rules:
    1. Empty targets -> DRAFT
    2. Any target is PUBLISHING -> PUBLISHING (in-flight publishing takes priority)
    3. All targets are PUBLISHED -> PUBLISHED
    4. At least one target is PUBLISHED (and remaining are not all published) -> PARTIALLY_PUBLISHED
       (e.g., PUBLISHED + SCHEDULED, PUBLISHED + FAILED, PUBLISHED + DRAFT, PUBLISHED + CANCELLED)
    5. Any target is SCHEDULED -> SCHEDULED (actively queued for scheduled publication)
    6. All targets are FAILED -> FAILED
    7. All targets are CANCELLED -> CANCELLED
    8. Any target is FAILED (with remaining DRAFT/CANCELLED, no SCHEDULED/PUBLISHED) -> FAILED
    9. Default fallback -> DRAFT
    """
    if not target_statuses:
        return PostStatus.DRAFT

    normalized = [PostTargetStatus(s) if isinstance(s, str) else s for s in target_statuses]

    if any(s == PostTargetStatus.PUBLISHING for s in normalized):
        return PostStatus.PUBLISHING

    if all(s == PostTargetStatus.PUBLISHED for s in normalized):
        return PostStatus.PUBLISHED

    if any(s == PostTargetStatus.PUBLISHED for s in normalized):
        return PostStatus.PARTIALLY_PUBLISHED

    if any(s == PostTargetStatus.SCHEDULED for s in normalized):
        return PostStatus.SCHEDULED

    if all(s == PostTargetStatus.FAILED for s in normalized):
        return PostStatus.FAILED

    if all(s == PostTargetStatus.CANCELLED for s in normalized):
        return PostStatus.CANCELLED

    if any(s == PostTargetStatus.FAILED for s in normalized):
        return PostStatus.FAILED

    return PostStatus.DRAFT

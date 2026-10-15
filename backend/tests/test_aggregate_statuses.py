from app.models.enums import (
    PostStatus,
    PostTargetStatus,
    compute_aggregate_post_status,
)


def test_empty_targets_returns_draft():
    assert compute_aggregate_post_status([]) == PostStatus.DRAFT


def test_publishing_takes_precedence():
    # Any publishing target takes immediate priority
    assert compute_aggregate_post_status([PostTargetStatus.PUBLISHING, PostTargetStatus.DRAFT]) == PostStatus.PUBLISHING
    assert compute_aggregate_post_status([PostTargetStatus.PUBLISHING, PostTargetStatus.PUBLISHED, PostTargetStatus.FAILED]) == PostStatus.PUBLISHING


def test_all_published_returns_published():
    assert compute_aggregate_post_status([PostTargetStatus.PUBLISHED, PostTargetStatus.PUBLISHED]) == PostStatus.PUBLISHED
    assert compute_aggregate_post_status([PostTargetStatus.PUBLISHED]) == PostStatus.PUBLISHED


def test_partially_published_conditions():
    assert compute_aggregate_post_status([PostTargetStatus.PUBLISHED, PostTargetStatus.FAILED]) == PostStatus.PARTIALLY_PUBLISHED
    assert compute_aggregate_post_status([PostTargetStatus.PUBLISHED, PostTargetStatus.DRAFT]) == PostStatus.PARTIALLY_PUBLISHED
    assert compute_aggregate_post_status([PostTargetStatus.PUBLISHED, PostTargetStatus.SCHEDULED]) == PostStatus.PARTIALLY_PUBLISHED
    assert compute_aggregate_post_status([PostTargetStatus.PUBLISHED, PostTargetStatus.CANCELLED]) == PostStatus.PARTIALLY_PUBLISHED


def test_scheduled_conditions():
    assert compute_aggregate_post_status([PostTargetStatus.SCHEDULED, PostTargetStatus.DRAFT]) == PostStatus.SCHEDULED
    assert compute_aggregate_post_status([PostTargetStatus.SCHEDULED, PostTargetStatus.SCHEDULED]) == PostStatus.SCHEDULED


def test_failed_conditions():
    assert compute_aggregate_post_status([PostTargetStatus.FAILED, PostTargetStatus.FAILED]) == PostStatus.FAILED
    assert compute_aggregate_post_status([PostTargetStatus.FAILED, PostTargetStatus.DRAFT]) == PostStatus.FAILED


def test_cancelled_conditions():
    assert compute_aggregate_post_status([PostTargetStatus.CANCELLED, PostTargetStatus.CANCELLED]) == PostStatus.CANCELLED


def test_string_inputs_normalized():
    assert compute_aggregate_post_status(["published", "published"]) == PostStatus.PUBLISHED
    assert compute_aggregate_post_status(["published", "failed"]) == PostStatus.PARTIALLY_PUBLISHED
    assert compute_aggregate_post_status(["draft", "draft"]) == PostStatus.DRAFT

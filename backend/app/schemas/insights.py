from pydantic import BaseModel, Field


class InsightsSummary(BaseModel):
    total_posts: int
    total_targets: int
    status_distribution: dict[str, int] = Field(default_factory=dict)
    platform_distribution: dict[str, int] = Field(default_factory=dict)
    publishing_velocity_posts_per_day: float = 0.0
    success_rate_percentage: float = 0.0
    total_impressions: int = 0
    total_engagements: int = 0

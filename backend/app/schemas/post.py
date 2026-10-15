from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import PostStatus, PostTargetStatus, SocialPlatform


class PostTargetCreate(BaseModel):
    platform: SocialPlatform
    custom_content: str | None = None
    scheduled_at: datetime | None = None


class PostCreate(BaseModel):
    content: str = Field(..., description="Master text content of the post")
    target_platforms: list[SocialPlatform] = Field(
        ...,
        min_length=1,
        description="List of target platforms to publish to (at least one required)",
    )
    custom_contents: dict[SocialPlatform, str] | None = Field(
        default=None,
        description="Optional platform-specific content overrides",
    )
    media_urls: list[str] = Field(default_factory=list, description="List of media asset URLs")
    scheduled_at: datetime | None = Field(
        default=None,
        description="Optional scheduled time for publication",
    )


class PostUpdate(BaseModel):
    content: str | None = None
    media_urls: list[str] | None = None
    scheduled_at: datetime | None = None


class PostTargetUpdate(BaseModel):
    custom_content: str | None = None


class PostTargetAdd(BaseModel):
    platform: SocialPlatform
    custom_content: str | None = None



class PostScheduleRequest(BaseModel):
    scheduled_at: datetime = Field(..., description="Target time for scheduled publication")


class PostTargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    platform: SocialPlatform
    custom_content: str | None = None
    status: PostTargetStatus
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    simulated_platform_post_id: str | None = None
    error_message: str | None = None
    execution_log: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    content: str
    media_urls: list[str] = Field(default_factory=list)
    status: PostStatus
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    targets: list[PostTargetResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PostPublishResponse(BaseModel):
    post_id: uuid.UUID
    status: PostStatus
    published_at: datetime | None = None
    targets: list[PostTargetResponse] = Field(default_factory=list)

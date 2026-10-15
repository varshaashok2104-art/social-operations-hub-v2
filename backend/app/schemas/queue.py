import uuid
from pydantic import BaseModel, Field
from app.schemas.post import PostResponse


class QueueResponse(BaseModel):
    items: list[PostResponse]
    total: int
    counts_by_status: dict[str, int] = Field(default_factory=dict)


class QueuePublishDueResponse(BaseModel):
    processed_count: int
    published_count: int
    failed_count: int
    post_ids: list[uuid.UUID] = Field(default_factory=list)

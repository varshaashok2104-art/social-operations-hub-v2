from datetime import datetime
import uuid
from pydantic import BaseModel, Field
from app.models.enums import PostStatus, SocialPlatform


class CalendarPostItem(BaseModel):
    id: uuid.UUID
    content: str
    status: PostStatus
    scheduled_at: datetime
    platforms: list[SocialPlatform] = Field(default_factory=list)
    media_count: int = 0


class CalendarResponse(BaseModel):
    start_date: datetime
    end_date: datetime
    total_posts: int
    posts: list[CalendarPostItem]

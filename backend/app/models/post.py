import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.enums import (
    PostStatus,
    PostTargetStatus,
    SocialPlatform,
    compute_aggregate_post_status,
)

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_posts_workspace_id"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    media_urls: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    status: Mapped[PostStatus] = mapped_column(
        SAEnum(
            PostStatus,
            name="ck_posts_status",
            native_enum=False,
            create_constraint=True,
            length=30,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PostStatus.DRAFT,
        server_default=text(f"'{PostStatus.DRAFT.value}'"),
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="posts",
    )
    targets: Mapped[list["PostTarget"]] = relationship(
        "PostTarget",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_posts_workspace_created_at", "workspace_id", text("created_at DESC")),
        Index("ix_posts_workspace_scheduled_at", "workspace_id", "scheduled_at"),
        Index("ix_posts_workspace_status", "workspace_id", "status"),
    )

    def sync_status(self) -> PostStatus:
        """Pure synchronization of aggregate status based on child targets."""
        self.status = compute_aggregate_post_status([t.status for t in self.targets])
        return self.status

    def __repr__(self) -> str:
        return f"<Post id={self.id} workspace_id={self.workspace_id} status={self.status.value}>"


class PostTarget(Base, TimestampMixin):
    __tablename__ = "post_targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE", name="fk_post_targets_post_id"),
        nullable=False,
    )
    platform: Mapped[SocialPlatform] = mapped_column(
        SAEnum(
            SocialPlatform,
            name="ck_post_targets_platform",
            native_enum=False,
            create_constraint=True,
            length=30,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    custom_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[PostTargetStatus] = mapped_column(
        SAEnum(
            PostTargetStatus,
            name="ck_post_targets_status",
            native_enum=False,
            create_constraint=True,
            length=30,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PostTargetStatus.DRAFT,
        server_default=text(f"'{PostTargetStatus.DRAFT.value}'"),
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    simulated_platform_post_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    execution_log: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    metrics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="targets",
    )

    __table_args__ = (
        UniqueConstraint("post_id", "platform", name="uq_post_targets_post_platform"),
        Index("ix_post_targets_status_scheduled_at", "status", "scheduled_at"),
        Index("ix_post_targets_platform_status", "platform", "status"),
    )

    def __repr__(self) -> str:
        return f"<PostTarget id={self.id} post_id={self.post_id} platform={self.platform.value} status={self.status.value}>"

import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import WorkspaceMember


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    members: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("slug", name="uq_workspaces_slug"),
    )

    def __repr__(self) -> str:
        return f"<Workspace id={self.id} slug={self.slug!r} name={self.name!r}>"

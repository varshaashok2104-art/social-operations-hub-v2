import uuid
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    memberships: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


class WorkspaceMember(Base, TimestampMixin):
    __tablename__ = "workspace_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_workspace_members_workspace_id"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_workspace_members_user_id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="owner", server_default=text("'owner'"))

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="members",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="memberships",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
        Index("ix_workspace_members_user_id", "user_id"),
        Index("ix_workspace_members_workspace_id", "workspace_id"),
    )

    def __repr__(self) -> str:
        return f"<WorkspaceMember workspace_id={self.workspace_id} user_id={self.user_id} role={self.role}>"

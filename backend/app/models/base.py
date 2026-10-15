from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """
    Mixin providing created_at and updated_at timestamp columns.

    NOTE: updated_at uses SQLAlchemy ORM-managed `onupdate=func.now()` behavior,
    not a universal PostgreSQL database trigger. Direct SQL updates bypassing the ORM
    must set updated_at explicitly.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

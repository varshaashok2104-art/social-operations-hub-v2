from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str | None = Field(None, max_length=100)
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    role: str = "member"
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str | None = None
    role: str
    created_at: datetime


class WorkspaceMemberAdd(BaseModel):
    email: str
    role: str = "member"

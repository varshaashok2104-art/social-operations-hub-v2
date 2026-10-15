import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_workspace_membership
from app.core.database import get_db_session
from app.models.user import User, WorkspaceMember
from app.models.workspace import Workspace
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


def generate_slug(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name.lower()).strip()
    slug = re.sub(r"[-\s]+", "-", cleaned)
    return slug or "workspace"


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    base_slug = data.slug.strip() if data.slug else generate_slug(data.name)
    # Ensure unique slug
    final_slug = base_slug
    check_stmt = select(Workspace).where(Workspace.slug == final_slug)
    res = await db.execute(check_stmt)
    if res.scalar_one_or_none():
        final_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    workspace = Workspace(
        name=data.name.strip(),
        slug=final_slug,
        description=data.description,
    )
    db.add(workspace)
    await db.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(member)
    await db.commit()
    await db.refresh(workspace)

    resp = WorkspaceResponse.model_validate(workspace)
    resp.role = "owner"
    return resp


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == current_user.id)
        .order_by(Workspace.created_at.desc())
    )
    result = await db.execute(stmt)
    workspaces_with_roles = result.all()

    items = []
    for ws, role in workspaces_with_roles:
        resp = WorkspaceResponse.model_validate(ws)
        resp.role = role
        items.append(resp)
    return items


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    resp = WorkspaceResponse.model_validate(workspace)
    resp.role = membership.role
    return resp


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: uuid.UUID,
    data: WorkspaceUpdate,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    if membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners or admins can update workspace settings",
        )

    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    if data.name is not None:
        workspace.name = data.name.strip()
    if data.description is not None:
        workspace.description = data.description

    await db.commit()
    await db.refresh(workspace)

    resp = WorkspaceResponse.model_validate(workspace)
    resp.role = membership.role
    return resp


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    if membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners can delete a workspace",
        )

    stmt = select(Workspace).where(Workspace.id == workspace_id)
    result = await db.execute(stmt)
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    await db.delete(workspace)
    await db.commit()
    return None


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: uuid.UUID,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = (
        select(WorkspaceMember, User)
        .join(User, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    members = []
    for member, user in rows:
        members.append(
            WorkspaceMemberResponse(
                id=member.id,
                workspace_id=member.workspace_id,
                user_id=member.user_id,
                email=user.email,
                full_name=user.full_name,
                role=member.role,
                created_at=member.created_at,
            )
        )
    return members


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_workspace_member(
    workspace_id: uuid.UUID,
    data: WorkspaceMemberAdd,
    membership: WorkspaceMember = Depends(get_workspace_membership),
    db: AsyncSession = Depends(get_db_session),
):
    if membership.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners or admins can add members",
        )

    # Find user by email
    user_stmt = select(User).where(User.email == data.email.lower().strip())
    user_res = await db.execute(user_stmt)
    target_user = user_res.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email '{data.email}' not found",
        )

    # Check if user already is a member
    existing_stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == target_user.id,
    )
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this workspace",
        )

    new_member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=target_user.id,
        role=data.role,
    )
    db.add(new_member)
    await db.commit()
    await db.refresh(new_member)

    return WorkspaceMemberResponse(
        id=new_member.id,
        workspace_id=new_member.workspace_id,
        user_id=new_member.user_id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=new_member.role,
        created_at=new_member.created_at,
    )

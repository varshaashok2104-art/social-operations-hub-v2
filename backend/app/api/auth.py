import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User, WorkspaceMember
from app.models.workspace import Workspace
from app.schemas.auth import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db_session),
):
    # Check if user already exists
    stmt = select(User).where(User.email == data.email.lower().strip())
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        )

    # Create new user
    user = User(
        email=data.email.lower().strip(),
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Automatically create default workspace for the new user
    slug_suffix = uuid.uuid4().hex[:6]
    display_name = data.full_name.split()[0] if data.full_name else "Personal"
    workspace = Workspace(
        name=f"{display_name}'s Workspace",
        slug=f"{display_name.lower()}-{slug_suffix}",
        description="Default workspace created upon registration",
    )
    db.add(workspace)
    await db.flush()

    # Add user as workspace owner
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="owner",
    )
    db.add(member)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(User).where(User.email == data.email.lower().strip())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account",
        )

    access_token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

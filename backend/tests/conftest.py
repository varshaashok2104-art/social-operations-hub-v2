import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import engine, get_db_session
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.user import User, WorkspaceMember
from app.models.workspace import Workspace
from app.services.publisher import sandbox_publisher


@pytest.fixture(autouse=True)
def configure_test_environment(monkeypatch: pytest.MonkeyPatch):
    # Set simulated latency to 0ms for fast, deterministic testing
    monkeypatch.setattr(settings, "SIMULATED_NETWORK_LATENCY_MS", 0)
    monkeypatch.setattr(sandbox_publisher, "latency_ms", 0)


@pytest.fixture
async def db_session():
    """
    Provides an isolated transaction for each test using savepoints.
    Automatically rolls back upon test completion to guarantee no persistent state changes.
    """
    async with engine.connect() as connection:
        trans = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def async_client(db_session: AsyncSession):
    """
    Async HTTP test client with database dependency override to use the isolated test session.
    """
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
async def test_user_factory(db_session: AsyncSession):
    """Factory fixture to create test users with default workspace and JWT token."""
    async def _create_user(email: str = "test@example.com", password: str = "secret1234", full_name: str = "Test User"):
        user = User(
            email=email.lower().strip(),
            hashed_password=get_password_hash(password),
            full_name=full_name,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        workspace = Workspace(
            name=f"{full_name}'s Workspace",
            slug=f"ws-{user.id.hex[:8]}",
            description="Test workspace",
        )
        db_session.add(workspace)
        await db_session.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role="owner",
        )
        db_session.add(member)
        await db_session.commit()
        await db_session.refresh(user)
        await db_session.refresh(workspace)

        token = create_access_token(subject=user.id)
        headers = {"Authorization": f"Bearer {token}"}
        return {
            "user": user,
            "workspace": workspace,
            "token": token,
            "headers": headers,
            "password": password,
        }

    return _create_user


@pytest.fixture(autouse=True)
async def cleanup_database_engine():
    yield
    await engine.dispose()

import pytest
import os
import tempfile
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing"
os.environ["LOG_DIR"] = os.path.join(_tmp, "logs")
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["VECTOR_DB_PATH"] = os.path.join(_tmp, "vector_store")

from app.models import Base, User
from app.database import get_db
from app.routers.auth import pwd_context
from app.main import app

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestSession = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

async def override_get_db():
    async with TestSession() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.fixture
async def auth_client(client):
    """已登录管理员客户端"""
    await client.post("/api/auth/init")
    resp = await client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client

@pytest.fixture
async def user_client(client):
    """已登录普通用户客户端（无审核权限），使用独立HTTP客户端"""
    async with TestSession() as session:
        user = User(username="regular", hashed_password=pwd_context.hash("user123"), role="user")
        session.add(user)
        await session.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/auth/login", data={"username": "regular", "password": "user123"})
        token = resp.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c

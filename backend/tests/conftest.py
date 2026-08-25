import pytest
import os
import tempfile
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 使用内存数据库
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing"
# 上传目录隔离到临时目录，避免写入 /data
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="kb_test_uploads_")

from app.models import Base
from app.database import get_db
from app.main import app
from app.services.embedding_service import EmbeddingService

# 测试环境禁用向量模型加载（避免网络下载），搜索相关用例自行 mock
EmbeddingService._load_model = lambda self: False

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
    """创建已认证的客户端"""
    await client.post("/api/auth/init")
    resp = await client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client

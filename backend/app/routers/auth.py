from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models import User
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str

def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user = await db.get(User, payload.get("sub"))
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/login", response_model=Token, summary="用户登录", description="使用用户名和密码登录，返回JWT访问令牌")
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()
    if not user or not pwd_context.verify(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"access_token": create_token({"sub": user.id}), "token_type": "bearer"}

@router.post("/init", summary="初始化管理员", description="创建默认管理员账号（admin/admin123），仅首次调用有效")
async def init_admin(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == "admin"))
    if result.scalar_one_or_none():
        return {"message": "Admin already exists"}
    admin = User(username="admin", hashed_password=pwd_context.hash("admin123"), role="admin")
    db.add(admin)
    await db.commit()
    return {"message": "Admin created", "username": "admin", "password": "admin123"}

@router.get("/me", summary="获取当前用户", description="根据JWT令牌获取当前登录用户信息")
async def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "role": user.role}

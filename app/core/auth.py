from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from app.models import GlobalUser, UserRole
from app.core.security import verify_password
from jose import jwt
from datetime import datetime, timedelta
from app.core.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создает JWT токен"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def authenticate_user(db, username: str, password: str):
    """Аутентифицирует пользователя - БЕЗ аннотации AsyncSession"""
    result = await db.execute(
        select(GlobalUser).where(GlobalUser.username == username)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    if not user.is_active:
        return None
    
    if verify_password(password, user.password_hash):
        return user
    return None

async def get_current_user(request: Request, db):
    """Получает текущего пользователя из токена - БЕЗ аннотации AsyncSession"""
    token = request.cookies.get("access_token")
    logger.info(f"🔍 Token found: {token is not None}")
    
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str = payload.get("sub")
        logger.info(f"🔍 User ID from token: {user_id_str}")
        
        if user_id_str is None:
            return None
        
        user_id = int(user_id_str)
    except jwt.JWTError as e:
        logger.error(f"❌ JWT decode error: {e}")
        return None
    except ValueError as e:
        logger.error(f"❌ Invalid user ID format: {e}")
        return None
    
    result = await db.execute(
        select(GlobalUser).where(GlobalUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    logger.info(f"🔍 User found in DB: {user is not None}")
    return user

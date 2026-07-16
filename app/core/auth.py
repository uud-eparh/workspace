from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import GlobalUser, Membership, UserRole
from app.core.security import verify_password
from app.core.database import AsyncSessionLocal
from jose import jwt
from datetime import datetime, timedelta
from app.core.config import settings
from typing import Optional, Tuple
import uuid
import logging

logger = logging.getLogger(__name__)

# ===== JWT =====

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

# ===== Аутентификация =====

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Tuple[Optional[GlobalUser], Optional[uuid.UUID], Optional[str]]:
    """
    Аутентифицирует пользователя по логину и паролю.
    Возвращает: (пользователь, tenant_id, ошибка)
    """
    # 1. Ищем пользователя
    result = await db.execute(
        select(GlobalUser).where(GlobalUser.username == username)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return None, None, "Неверный логин или пароль"
    
    if not user.is_active:
        return None, None, "Пользователь заблокирован"
    
    # 2. Особый случай: SUPER_ADMIN входит без слоя
    if user.role == UserRole.SUPER_ADMIN:
        # Для SUPER_ADMIN проверяем пароль через отдельный механизм
        # Временно: admin123
        if password == "admin123":
            return user, None, None
        return None, None, "Неверный логин или пароль"
    
    # 3. Ищем все записи membership для обычных пользователей
    result = await db.execute(
        select(Membership).where(Membership.user_id == user.id)
    )
    memberships = result.scalars().all()
    
    if not memberships:
        return None, None, "У вас нет доступа ни к одному слою. Обратитесь к администратору."
    
    # 4. Проверяем пароль против всех слоев
    matching_memberships = []
    for membership in memberships:
        if verify_password(password, membership.layer_access_hash):
            matching_memberships.append(membership)
    
    # 5. Если пароль подошел к одному или нескольким слоям
    if len(matching_memberships) == 1:
        membership = matching_memberships[0]
        if not membership.is_active:
            return None, None, "Доступ к этому слою заблокирован"
        return user, membership.tenant_id, None
    
    if len(matching_memberships) > 1:
        return None, None, "Один пароль используется для нескольких слоев. Обратитесь к администратору."
    
    # 6. Если пароль не подошел ни к одному слою
    return None, None, "Неверный логин или пароль"

# ===== Получение текущего пользователя =====

async def get_current_user(request: Request, db: AsyncSession) -> Optional[GlobalUser]:
    """Получает текущего пользователя из токена"""
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = uuid.UUID(user_id_str)
    except (jwt.JWTError, ValueError, TypeError):
        return None
    
    result = await db.execute(
        select(GlobalUser).where(GlobalUser.id == user_id)
    )
    user = result.scalar_one_or_none()
    return user

async def get_current_tenant(request: Request) -> Optional[uuid.UUID]:
    """Получает текущий tenant_id из токена"""
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        tenant_id_str: str = payload.get("tenant_id")
        if not tenant_id_str:
            return None
        if tenant_id_str == "null" or tenant_id_str == "":
            return None
        return uuid.UUID(tenant_id_str)
    except (jwt.JWTError, ValueError, TypeError):
        return None

# ===== Проверка роли внутри слоя =====

async def get_current_user_role(request: Request, db: AsyncSession) -> Optional[str]:
    """Получает роль текущего пользователя в текущем слое"""
    user = await get_current_user(request, db)
    tenant_id = await get_current_tenant(request)
    
    if not user or not tenant_id:
        return None
    
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.tenant_id == tenant_id
        )
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        return None
    
    return membership.role

async def is_chief(request: Request, db: AsyncSession) -> bool:
    """Проверяет, является ли пользователь Chief в текущем слое"""
    role = await get_current_user_role(request, db)
    return role == "chief"

# ===== Проверка прав =====

async def get_current_user_with_tenant(request: Request, db: AsyncSession) -> Tuple[Optional[GlobalUser], Optional[uuid.UUID]]:
    """Получает пользователя и tenant_id из токена"""
    user = await get_current_user(request, db)
    tenant_id = await get_current_tenant(request)
    return user, tenant_id

async def get_current_active_user(
    current_user: GlobalUser = Depends(get_current_user)
):
    """Проверяет, что пользователь активен"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# ===== Вспомогательные функции =====

async def get_membership_for_user(db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[Membership]:
    """Получает membership для пользователя в конкретном слое"""
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()

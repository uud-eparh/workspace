from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import GlobalUser, UserRole
from app.core.security import get_password_hash
from app.schemas.user import UserCreate, UserUpdate
from typing import Optional

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users(
        self, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ):
        """Получить список пользователей"""
        query = select(GlobalUser)
        
        if search:
            query = query.where(
                GlobalUser.username.ilike(f"%{search}%") |
                GlobalUser.email.ilike(f"%{search}%")
            )
        
        count_query = select(func.count()).select_from(GlobalUser)
        if search:
            count_query = count_query.where(
                GlobalUser.username.ilike(f"%{search}%") |
                GlobalUser.email.ilike(f"%{search}%")
            )
        
        total = await self.db.scalar(count_query)
        
        query = query.offset(skip).limit(limit).order_by(GlobalUser.id)
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        return users, total

    async def get_user_by_id(self, user_id: int):
        """Получить пользователя по ID"""
        result = await self.db.execute(
            select(GlobalUser).where(GlobalUser.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str):
        """Получить пользователя по имени"""
        result = await self.db.execute(
            select(GlobalUser).where(GlobalUser.username == username)
        )
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate):
        """Создать нового пользователя"""
        # Преобразуем строку роли в Enum
        role_map = {
            'MASTER_ADMIN': UserRole.MASTER_ADMIN,
            'MASTER_USER': UserRole.MASTER_USER,
            'USER': UserRole.USER
        }
        role = role_map.get(user_data.role, UserRole.USER)
        
        user = GlobalUser(
            username=user_data.username,
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role=role,
            is_active=user_data.is_active
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user(self, user_id: int, user_data: UserUpdate):
        """Обновить пользователя"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        
        update_data = user_data.model_dump(exclude_unset=True)
        
        if "password" in update_data and update_data["password"]:
            user.password_hash = get_password_hash(update_data["password"])
            del update_data["password"]
        
        if "role" in update_data and update_data["role"]:
            role_map = {
                'MASTER_ADMIN': UserRole.MASTER_ADMIN,
                'MASTER_USER': UserRole.MASTER_USER,
                'USER': UserRole.USER
            }
            user.role = role_map.get(update_data["role"], UserRole.USER)
            del update_data["role"]
        
        for field, value in update_data.items():
            if value is not None:
                setattr(user, field, value)
        
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete_user(self, user_id: int):
        """Удалить пользователя"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        await self.db.delete(user)
        await self.db.commit()
        return True

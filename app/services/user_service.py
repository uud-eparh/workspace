from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import GlobalUser, UserRole
from app.schemas.user import UserCreate, UserUpdate
from typing import Optional, List, Tuple
import uuid

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users(
        self, 
        skip: int = 0, 
        limit: int = 100,
        search: Optional[str] = None
    ) -> Tuple[List[GlobalUser], int]:
        """Получить список пользователей с пагинацией и поиском"""
        query = select(GlobalUser)
        
        if search:
            query = query.where(
                GlobalUser.username.ilike(f"%{search}%") |
                GlobalUser.full_name.ilike(f"%{search}%") |
                GlobalUser.email.ilike(f"%{search}%")
            )
        
        # Получаем общее количество
        count_query = select(func.count()).select_from(GlobalUser)
        if search:
            count_query = count_query.where(
                GlobalUser.username.ilike(f"%{search}%") |
                GlobalUser.full_name.ilike(f"%{search}%") |
                GlobalUser.email.ilike(f"%{search}%")
            )
        
        total = await self.db.scalar(count_query)
        
        # Получаем пользователей
        query = query.offset(skip).limit(limit).order_by(GlobalUser.created_at.desc())
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        return users, total

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[GlobalUser]:
        """Получить пользователя по ID"""
        result = await self.db.execute(
            select(GlobalUser).where(GlobalUser.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[GlobalUser]:
        """Получить пользователя по имени"""
        result = await self.db.execute(
            select(GlobalUser).where(GlobalUser.username == username)
        )
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate) -> GlobalUser:
        """Создать нового пользователя"""
        # Проверяем, существует ли пользователь
        existing = await self.get_user_by_username(user_data.username)
        if existing:
            raise ValueError(f"Пользователь с именем '{user_data.username}' уже существует")
        
        user = GlobalUser(
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            department=user_data.department,
            subdivision=user_data.subdivision,
            role=UserRole.USER,
            is_active=True
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user(self, user_id: uuid.UUID, user_data: UserUpdate) -> Optional[GlobalUser]:
        """Обновить пользователя"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        
        update_data = user_data.model_dump(exclude_unset=True)
        
        # Проверяем уникальность username
        if "username" in update_data and update_data["username"]:
            existing = await self.get_user_by_username(update_data["username"])
            if existing and existing.id != user_id:
                raise ValueError(f"Пользователь с именем '{update_data['username']}' уже существует")
        
        for field, value in update_data.items():
            if value is not None:
                setattr(user, field, value)
        
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def toggle_user_active(self, user_id: uuid.UUID) -> Optional[GlobalUser]:
        """Переключить статус активности пользователя"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None
        
        user.is_active = not user.is_active
        await self.db.commit()
        await self.db.refresh(user)
        return user

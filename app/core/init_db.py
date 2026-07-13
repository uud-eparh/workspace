from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import GlobalUser, UserRole
from app.core.security import get_password_hash
import logging

logger = logging.getLogger(__name__)

async def init_master_admin(db: AsyncSession) -> bool:
    """Создает мастер-администратора при первом запуске"""
    
    # Проверяем, есть ли пользователи
    result = await db.execute(select(GlobalUser))
    users = result.scalars().all()
    
    if users:
        logger.info("Users already exist, skipping master admin creation")
        return False
    
    # Создаем мастер-администратора
    admin_password = "admin123"  # Временный пароль, принудительно сменить при первом входе
    
    admin = GlobalUser(
        username="admin",
        email="admin@openledger.local",
        password_hash=get_password_hash(admin_password),
        role=UserRole.MASTER_ADMIN,
        is_active=True
    )
    
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    
    logger.info(f"✅ Master admin created successfully!")
    logger.info(f"   Username: admin")
    logger.info(f"   Password: {admin_password}")
    logger.info(f"   ⚠️  PLEASE CHANGE PASSWORD ON FIRST LOGIN!")
    
    return True

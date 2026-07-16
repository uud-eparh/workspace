from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import GlobalUser, Membership, UserRole
from app.core.security import get_password_hash
import logging

logger = logging.getLogger(__name__)

async def init_super_admin(db: AsyncSession) -> bool:
    """Создает суперадминистратора и первого руководителя при первом запуске"""
    
    # Проверяем, есть ли уже пользователи
    result = await db.execute(select(GlobalUser))
    existing_users = result.scalars().all()
    
    if existing_users:
        logger.info("✅ Пользователи уже существуют, пропускаем инициализацию")
        return False
    
    logger.info("👑 Создаем суперадминистратора...")
    
    # 1. Создаем суперадминистратора (без membership)
    admin = GlobalUser(
        username="super_admin",
        email="admin@openledger.local",
        full_name="Super Administrator",
        role=UserRole.SUPER_ADMIN,
        is_active=True
    )
    db.add(admin)
    await db.flush()
    logger.info(f"✅ Суперадминистратор создан: {admin.id}")
    logger.info(f"   Логин: super_admin")
    logger.info(f"   Пароль: admin123")
    
    # 2. Создаем первого руководителя
    logger.info("👤 Создаем первого руководителя...")
    
    chief = GlobalUser(
        username="chief",
        email="chief@openledger.local",
        full_name="Chief Administrator",
        role=UserRole.CHIEF,
        is_active=True
    )
    db.add(chief)
    await db.flush()
    logger.info(f"✅ Руководитель создан: {chief.id}")
    logger.info(f"   Логин: chief")
    
    # 3. Создаем глобальный доступ для chief (tenant_id = NULL)
    logger.info("🔐 Создаем глобальный доступ для руководителя...")
    
    global_membership = Membership(
        user_id=chief.id,
        tenant_id=None,
        role="chief",
        layer_access_hash=get_password_hash("chief123"),
        is_active=True
    )
    db.add(global_membership)
    logger.info(f"   Пароль для глобального доступа: chief123")
    
    await db.commit()
    
    logger.info("✅ Инициализация завершена!")
    logger.info("📋 Данные для входа:")
    logger.info(f"   Суперадминистратор: super_admin / admin123")
    logger.info(f"   Руководитель (глобально): chief / chief123")
    logger.info("ℹ️  Руководитель создает компании через 'Создать компанию'")
    logger.info("ℹ️  Для входа в компанию используется пароль, заданный при создании")
    
    return True

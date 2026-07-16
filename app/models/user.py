from sqlalchemy import Column, String, DateTime, Boolean, Enum, UUID
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, text
from app.models.base import Base
import enum

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    CHIEF = "chief"          # <-- НОВАЯ РОЛЬ
    USER = "user"

class GlobalUser(Base):
    __tablename__ = "global_users"
    
    id = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()"),
        index=True
    )
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    subdivision = Column(String(255), nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<GlobalUser {self.username} ({self.role})>"

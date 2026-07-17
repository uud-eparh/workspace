from sqlalchemy import Column, String, UUID, JSON, Boolean, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, text
from app.models.base import Base
import uuid

class CommonDictionary(Base):
    __tablename__ = "common_dictionaries"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        index=True
    )
    type = Column(String(50), nullable=False, index=True)  # units, currencies, countries, regions, cities
    code = Column(String(50), nullable=False)  # Код (уникален в пределах типа)
    name = Column(String(255), nullable=False)  # Название
    symbol = Column(String(50), nullable=True)  # Символ (опционально)
    extra_data = Column(JSON, nullable=True)  # Дополнительные поля (например, num_code для валют)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('type', 'code', name='uq_type_code'),
    )
    
    def __repr__(self):
        return f"<CommonDictionary {self.type}:{self.code} ({self.name})>"

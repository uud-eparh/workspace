from sqlalchemy import Column, String, UUID
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, text
from app.models.base import Base
import uuid

class Currency(Base):
    __tablename__ = "currencies"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        index=True
    )
    code = Column(String(3), unique=True, nullable=False)  # RUB, USD, EUR
    num_code = Column(String(3), nullable=True)  # 643, 840, 978
    name = Column(String(50), nullable=False)  # Российский рубль
    symbol = Column(String(5), nullable=True)  # ₽, $, €
    
    def __repr__(self):
        return f"<Currency {self.code} ({self.name})>"

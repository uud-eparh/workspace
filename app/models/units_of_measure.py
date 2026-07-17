from sqlalchemy import Column, String, UUID
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, text
from app.models.base import Base
import uuid

class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        index=True
    )
    code = Column(String(10), unique=True, nullable=False)  # шт, кг, м, л
    name = Column(String(50), nullable=False)  # Штука, Килограмм, Метр
    symbol = Column(String(20), nullable=True)  # шт, кг, м (увеличено до 20)
    
    def __repr__(self):
        return f"<UnitOfMeasure {self.code} ({self.name})>"

from sqlalchemy import Column, String, UUID, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, text
from app.models.base import Base
import uuid

class City(Base):
    __tablename__ = "cities"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        index=True
    )
    region_id = Column(PG_UUID(as_uuid=True), ForeignKey("regions.id"), nullable=False)
    code = Column(String(10), nullable=True)  # Код города (в т.ч. ФИАС)
    name = Column(String(100), nullable=False)  # Москва, Краснодар
    
    def __repr__(self):
        return f"<City {self.name}>"

from sqlalchemy import Column, String, UUID, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, text
from app.models.base import Base
import uuid

class Region(Base):
    __tablename__ = "regions"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        index=True
    )
    country_id = Column(PG_UUID(as_uuid=True), ForeignKey("countries.id"), nullable=False)
    code = Column(String(10), nullable=True)  # Код региона
    name = Column(String(100), nullable=False)  # Московская область
    
    def __repr__(self):
        return f"<Region {self.name}>"

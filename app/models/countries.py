from sqlalchemy import Column, String, UUID
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, text
from app.models.base import Base
import uuid

class Country(Base):
    __tablename__ = "countries"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        index=True
    )
    code = Column(String(2), unique=True, nullable=False)  # RU, US, DE
    name = Column(String(100), nullable=False)  # Россия, США, Германия
    
    def __repr__(self):
        return f"<Country {self.code} ({self.name})>"

from sqlalchemy import Column, DateTime, String, ForeignKey, UniqueConstraint, Boolean, UUID
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func, text
from app.models.base import Base

class Membership(Base):
    __tablename__ = "membership"
    
    id = Column(
        PG_UUID(as_uuid=True), 
        primary_key=True, 
        server_default=text("gen_random_uuid()"),
        index=True
    )
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("global_users.id"), nullable=False)
    tenant_id = Column(PG_UUID(as_uuid=True), ForeignKey("tenants_layers.id"), nullable=True)  # <-- nullable=True
    role = Column(String(50), nullable=False)
    layer_access_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'tenant_id', name='uq_user_tenant'),
    )
    
    def __repr__(self):
        return f"<Membership user={self.user_id} tenant={self.tenant_id}>"

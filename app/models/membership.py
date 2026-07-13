from sqlalchemy import Column, Integer, DateTime, String, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.models.base import Base

class Membership(Base):
    __tablename__ = "membership"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("global_users.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants_layers.id"), nullable=False)
    role = Column(String(50), nullable=False)
    layer_access_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'tenant_id', name='uq_user_tenant'),
    )
    
    def __repr__(self):
        return f"<Membership user={self.user_id} tenant={self.tenant_id}>"

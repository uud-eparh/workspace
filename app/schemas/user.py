from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    is_active: bool = True

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    role: str = Field(default="USER")
    
    @validator('role')
    def validate_role(cls, v):
        allowed = ['MASTER_ADMIN', 'MASTER_USER', 'USER']
        if v not in allowed:
            raise ValueError(f'Роль должна быть одной из: {", ".join(allowed)}')
        return v

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)
    
    @validator('role')
    def validate_role(cls, v):
        if v is not None:
            allowed = ['MASTER_ADMIN', 'MASTER_USER', 'USER']
            if v not in allowed:
                raise ValueError(f'Роль должна быть одной из: {", ".join(allowed)}')
        return v

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    class Config:
        from_attributes = True

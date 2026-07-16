from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
import uuid

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    subdivision: Optional[str] = Field(None, max_length=255)
    is_active: bool = True

class UserCreate(UserBase):
    username: str = Field(..., min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    subdivision: Optional[str] = Field(None, max_length=255)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    subdivision: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    subdivision: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

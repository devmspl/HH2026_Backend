from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models.user import UserRole, SurveyStatus
from datetime import datetime

# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True
    full_name: Optional[str] = None
    role: Optional[UserRole] = UserRole.AGENT
    last_lat: Optional[float] = None
    last_lng: Optional[float] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    parent_id: Optional[int] = None

# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    password: str

# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDBBase(UserBase):
    id: Optional[int] = None

    class Config:
        from_attributes = True

# Additional properties to return via API
class User(UserInDBBase):
    pass

# Additional properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str
# Survey schemas
class SurveyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    status: Optional[SurveyStatus] = SurveyStatus.DRAFT

class SurveyCreate(SurveyBase):
    pass

class SurveyOut(SurveyBase):
    id: int
    created_by: int
    created_at: datetime

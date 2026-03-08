from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models.user import UserRole
from datetime import datetime

from .role import Role

# Shared properties (email as str on output so any DB value e.g. *@seed.local is accepted)
class UserBase(BaseModel):
    email: Optional[str] = None
    is_active: Optional[bool] = True
    full_name: Optional[str] = None
    role: Optional[UserRole] = UserRole.AGENT
    role_id: Optional[int] = None
    last_lat: Optional[float] = None
    last_lng: Optional[float] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    parent_id: Optional[int] = None
    avatar_url: Optional[str] = None
    permissions: Optional[str] = None # JSON string of allowed menu IDs
    age: Optional[int] = None
    sex: Optional[str] = None
    profession: Optional[str] = None
    nrc: Optional[str] = None
    province_id: Optional[int] = None
    district_id: Optional[int] = None
    region_id: Optional[int] = None
    camp_id: Optional[int] = None

# Properties to receive via API on creation (strict email on input)
class UserCreate(UserBase):
    email: EmailStr  # validated on create/register
    password: str

# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None

class UserInDBBase(UserBase):
    id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

# Additional properties to return via API
class User(UserInDBBase):
    created_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    is_deleted: Optional[bool] = False
    deleted_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    approver_details: Optional[dict] = None  # Will contain {id, full_name, role, avatar_url}
    system_role: Optional[Role] = None

# Additional properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str

# Survey schemas
class SurveyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str # Survey Title
    # Store as plain string for compatibility with existing DB/frontend values
    # e.g. "National Crops Survey" / "Regional Crops Survey"
    form_type: str = "National Crops Survey"
    description: Optional[str] = None # Survey Description / Objective
    # "All Agents" or "Selected Agents"
    target_respondents: str = "All Agents"
    instructions: Optional[str] = None # Instructions for Agents
    allow_edit: bool = False # Allow Edit After Submission?
    # "Yes", "Optional", "No"
    attachment_required: str = "Optional"
    # "draft", "active", "ended"
    status: str = "draft"

class SurveyCreate(SurveyBase):
    target_user_ids: List[int] = []

class SurveyUpdate(BaseModel):
    name: Optional[str] = None
    form_type: Optional[str] = None
    description: Optional[str] = None
    target_respondents: Optional[str] = None
    instructions: Optional[str] = None
    allow_edit: Optional[bool] = None
    attachment_required: Optional[str] = None
    status: Optional[str] = None
    target_user_ids: Optional[List[int]] = None

class SurveyOut(SurveyBase):
    id: int
    created_by: int
    created_at: datetime
    target_user_ids: Optional[List[int]] = None # We can map this manually or use a property

from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models.user import UserRole, SurveyStatus, SurveyType, TargetRespondents, AttachmentRequirement
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
    avatar_url: Optional[str] = None

# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
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

# Additional properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str

# Survey schemas
class SurveyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str # Survey Title
    form_type: SurveyType = SurveyType.NATIONAL # Survey Type
    description: Optional[str] = None # Survey Description / Objective
    target_respondents: TargetRespondents = TargetRespondents.ALL # Target Respondents
    instructions: Optional[str] = None # Instructions for Agents
    allow_edit: bool = False # Allow Edit After Submission?
    attachment_required: AttachmentRequirement = AttachmentRequirement.OPTIONAL # Attachment Required?
    status: SurveyStatus = SurveyStatus.DRAFT

class SurveyCreate(SurveyBase):
    target_user_ids: List[int] = []

class SurveyUpdate(BaseModel):
    name: Optional[str] = None
    form_type: Optional[SurveyType] = None
    description: Optional[str] = None
    target_respondents: Optional[TargetRespondents] = None
    instructions: Optional[str] = None
    allow_edit: Optional[bool] = None
    attachment_required: Optional[AttachmentRequirement] = None
    status: Optional[SurveyStatus] = None
    target_user_ids: Optional[List[int]] = None

class SurveyOut(SurveyBase):
    id: int
    created_by: int
    created_at: datetime
    target_user_ids: Optional[List[int]] = None # We can map this manually or use a property

from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class DashboardStats(BaseModel):
    total_agents: int
    active_agents: int
    inactive_agents: int
    total_reports: int
    recent_notifications: List[dict]
    pending_reports: int
    approved_reports: int
    rejected_reports: int
    report_trend: List[dict]

class AgentLocation(BaseModel):
    id: int
    full_name: str
    lat: Optional[float]
    lng: Optional[float]
    status: str
    last_seen: Optional[datetime]

class ReportBase(BaseModel):
    title: str
    description: Optional[str]
    gps_lat: float
    gps_lng: float

class ReportCreate(ReportBase):
    agent_id: int
    survey_id: int
    survey_responses: Optional[dict] = None # For SMS notification
    media: Optional[List[dict]] = None # List of {url, type, name}
    status: Optional[str] = "pending"

class ReportUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    media: Optional[List[dict]] = None
    survey_id: Optional[int] = None

class ReportEditHistory(BaseModel):
    id: int
    changes: str
    user_id: int
    user_name: Optional[str] = None
    timestamp: datetime
    class Config:
        from_attributes = True

class ReportMedia(BaseModel):
    id: int
    file_url: str
    file_type: Optional[str] = "image"
    file_name: Optional[str] = None
    class Config:
        from_attributes = True

class Report(ReportBase):
    id: int
    agent_id: int
    agent_name: Optional[str] = None
    agent_role: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    agent_avatar: Optional[str] = None
    status: str
    confirmation_no: str
    created_at: datetime
    media: List[ReportMedia] = []
    edits: List[ReportEditHistory] = []
    survey_id: Optional[int] = None
    survey_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class NotificationConfig(BaseModel):
    push_enabled: bool

class ChatMessage(BaseModel):
    id: int
    group_id: int
    sender_id: int
    sender_name: Optional[str] = None
    text: str
    timestamp: datetime
    class Config:
        from_attributes = True

class UserSmall(BaseModel):
    id: int
    full_name: str
    class Config:
        from_attributes = True

class ChatGroup(BaseModel):
    id: int
    name: str
    manager_id: int
    members: List[UserSmall] = []
    messages: List[ChatMessage] = []
    class Config:
        from_attributes = True

class AuditLog(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    action: str
    details: Optional[str]
    timestamp: datetime
    ip_address: Optional[str]
    class Config:
        from_attributes = True

class MediaItem(BaseModel):
    id: int
    report_id: int
    image_url: str
    agent_name: Optional[str] = None
    report_title: Optional[str] = None
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

from typing import List, Optional
from pydantic import BaseModel, ConfigDict
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
    agent_name: Optional[str] = None
    agent_role: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    survey_id: int
    survey_responses: Optional[dict] = None # For SMS notification
    media: Optional[List[dict]] = None # List of {url, type, name}
    status: Optional[str] = "pending"
    province_id: Optional[int] = None  # For Crop Domination Map (By Province)
    district_id: Optional[int] = None
    region_id: Optional[int] = None    # For Crop Domination Map (By Region)
    camp_id: Optional[int] = None      # For granular tracking


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
    province_id: Optional[int] = None
    district_id: Optional[int] = None
    region_id: Optional[int] = None
    camp_id: Optional[int] = None
    survey_responses: Optional[dict] = None

    class Config:
        from_attributes = True

class NotificationConfig(BaseModel):
    push_enabled: bool

class ChatMessage(BaseModel):
    id: int
    group_id: int
    sender_id: int
    sender_name: Optional[str] = None
    text: Optional[str] = None
    media_url: Optional[str] = None
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
    group_type: Optional[str] = None
    province_id: Optional[int] = None
    district_id: Optional[int] = None
    region_id: Optional[int] = None
    camp_id: Optional[int] = None
    members: List[UserSmall] = []
    messages: List[ChatMessage] = []
    class Config:
        from_attributes = True

class RegionMember(BaseModel):
    id: int
    name: str
    role: str
    region_id: Optional[int] = None
    district_id: Optional[int] = None
    province_id: Optional[int] = None
    class Config:
        from_attributes = True

class RegionGroupResponse(BaseModel):
    group_id: int
    group_name: str
    members: List[RegionMember]
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


class NationalCropRow(BaseModel):
    """
    One row for the National crops table.
    """
    crop_id: Optional[str] = None
    crop_name: str
    family_name: str
    yield_tonnes: float
    active_customers: Optional[int] = None
    participating_customers: Optional[int] = None
    percent_of_pcustomers: Optional[float] = None # % of Participating Customers
    percent_of_acustomers: Optional[float] = None # % of Active Customers


class NationalCropFamilyPie(BaseModel):
    """
    Aggregated data by crop family for pie / bar charts.
    """
    family_name: str
    total_yield_tonnes: float
    total_spoiled_responses: int
    active_customers: Optional[int] = None
    participating_customers: Optional[int] = None
    percent_of_pcustomers: Optional[float] = None
    percent_of_acustomers: Optional[float] = None


class NationalCropReport(BaseModel):
    """
    National-level crop report used by dashboard tables and charts.
    """
    total_farmers: int
    participating_farmers: int
    spoiled_responses: int
    rows: List[NationalCropRow]
    families: List[NationalCropFamilyPie]


class RegionalCropTallyRow(BaseModel):
    """One row for Regional crops tally table."""
    rcrop_id: Optional[str] = None
    crop_id: Optional[str] = None # Support both names for flexibility
    regional_crop_name: str
    family_name: str
    region_name: Optional[str] = None
    district_name: Optional[str] = None
    province_name: Optional[str] = None
    yield_tonnes: float
    active_customers: Optional[int] = None
    participating_customers: Optional[int] = None
    percent_of_pcustomers: Optional[float] = None
    percent_of_acustomers: Optional[float] = None


class RegionalCropTallyReport(BaseModel):
    """Regional crops tally report (by region)."""
    active_customers: int
    participating_customers: int
    spoiled_responses: int
    total_camps: int
    total_yield: float
    total_reports: int
    rows: List[RegionalCropTallyRow]

class TopFamilyRankRow(BaseModel):
    family_name: str
    province_count: int
    provinces: List[str]

class TopFamilyRankResponse(BaseModel):
    rows: List[TopFamilyRankRow]

class ProvinceDominance(BaseModel):
    province_id: int
    province_name: str
    dominant_family_name: str
    yield_tonnes: float

class RegionDominance(BaseModel):
    region_id: int
    region_name: str
    district_name: str
    province_name: str
    dominant_family_name: str
    yield_tonnes: float

class DominantCropMapResponse(BaseModel):
    by_province: List[ProvinceDominance]
    by_region: List[RegionDominance]

class RegionCount(BaseModel):
    id: int
    name: str
    count: int

class RegionReportingStatus(BaseModel):
    id: int
    name: str
    total_camps: int
    submitted_camps: int
    is_approved: bool
    status: str # RED, ORANGE, BLUE, GREEN

class DistrictSummary(BaseModel):
    total_farmers: int
    agents_by_region: List[RegionCount]
    customers_by_region: List[RegionCount]
    region_statuses: List[RegionReportingStatus]

class PaginatedReports(BaseModel):
    items: List[Report]
    total: int
    page: int
    limit: int
    pages: int
    model_config = ConfigDict(from_attributes=True)

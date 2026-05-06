import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, DateTime, Float, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMINISTRATOR = "ADMINISTRATOR"
    EXECUTIVE = "EXECUTIVE"
    NATIONAL = "NATIONAL"
    PROVINCIAL = "PROVINCIAL"
    DISTRICT = "DISTRICT"
    REGION = "REGION"
    CAMP = "CAMP"
    AGENT = "AGENT"

class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    DEACTIVATED = "deactivated"

class SystemRole(Base):
    __tablename__ = "system_roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    permissions = Column(Text, nullable=True) # JSON stored as text
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(String(50), default="AGENT", nullable=False)
    
    # Dynamic Role
    role_id = Column(Integer, ForeignKey("system_roles.id"), nullable=True)
    system_role = relationship("SystemRole", backref="users")

    # Status
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    account_status = Column(Enum(AccountStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), default=AccountStatus.ACTIVE)
    
    # Soft Delete
    is_deleted = Column(Boolean(), default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Permissions (JSON stored as text - Fallback or additional)
    permissions = Column(Text, nullable=True)
    
    # Approval Tracking
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Hierarchy
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    parent = relationship("User", remote_side=[id], backref="subordinates", foreign_keys=[parent_id])
    
    # Contact Info
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Last Known Location for GIS Tracking
    last_lat = Column(Float, nullable=True)
    last_lng = Column(Float, nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    location = Column(String(255), nullable=True) # Assigned area or address

    # Location hierarchy (for Agent, Camp, Region, District, Provincial users)
    camp_id = Column(Integer, ForeignKey("camps.id"), nullable=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)
    province_id = Column(Integer, ForeignKey("provinces.id"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)

    # Agent profile fields (when role = AGENT)
    age = Column(Integer, nullable=True)
    sex = Column(String(20), nullable=True)
    profession = Column(String(255), nullable=True)
    nrc = Column(String(50), nullable=True)  # National ID / NRC

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    reports = relationship("Report", back_populates="agent")
    notifications = relationship("NotificationLog", back_populates="recipient", foreign_keys="[NotificationLog.recipient_id]")

class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    status = Column(Enum(ReportStatus), default=ReportStatus.PENDING)
    
    # GPS data
    gps_lat = Column(Float, nullable=False)
    gps_lng = Column(Float, nullable=False)
    
    # Confirmation No. for quick tracking
    confirmation_no = Column(String(50), unique=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Store dynamic survey results as JSON string
    survey_data = Column(Text, nullable=True)

    # Location at time of report (from agent's assigned location)
    province_id = Column(Integer, ForeignKey("provinces.id"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)
    camp_id = Column(Integer, ForeignKey("camps.id"), nullable=True)

    agent = relationship("User", back_populates="reports")
    survey = relationship("Survey", backref="reports")
    media = relationship("ReportMedia", back_populates="report", cascade="all, delete-orphan")
    edits = relationship("ReportEditHistory", back_populates="report", cascade="all, delete-orphan")

class ReportMedia(Base):
    __tablename__ = "report_media"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    file_url = Column(Text, nullable=False)
    file_type = Column(String(50), nullable=True) # image, pdf, video, doc, etc.
    file_name = Column(String(255), nullable=True)
    
    report = relationship("Report", back_populates="media")

class ReportEditHistory(Base):
    __tablename__ = "report_edit_history"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    changes = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    report = relationship("Report", back_populates="edits")

class SurveyStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ENDED = "ended"

class SurveyType(str, enum.Enum):
    NATIONAL = "National Crops Survey"
    REGIONAL = "Regional Crops Survey"

class TargetRespondents(str, enum.Enum):
    ALL = "All Agents"
    SELECTED = "Selected Agents"

class AttachmentRequirement(str, enum.Enum):
    YES = "Yes"
    OPTIONAL = "Optional"
    NO = "No"

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False) # Survey Title
    # Store form_type as plain string for compatibility with existing data
    # Values are expected to be like "National Crops Survey" / "Regional Crops Survey"
    form_type = Column(String(255), nullable=False, default=SurveyType.NATIONAL.value) # Survey Type
    description = Column(Text, nullable=True) # Survey Description / Objective
    # Store target_respondents as plain string (e.g. "All Agents", "Selected Agents")
    target_respondents = Column(String(100), nullable=False, default=TargetRespondents.ALL.value)
    instructions = Column(Text, nullable=True) # Instructions for Agents
    allow_edit = Column(Boolean, default=False) # Allow Edit After Submission?
    # Store attachment_required as plain string ("Yes", "Optional", "No")
    attachment_required = Column(String(50), nullable=False, default=AttachmentRequirement.OPTIONAL.value)
    # Store status as plain string ("draft", "active", "ended")
    status = Column(String(50), nullable=False, default=SurveyStatus.DRAFT.value)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Target Users (for Selected Agents)
    target_users = relationship("User", secondary="survey_targets")

survey_targets = Table(
    "survey_targets",
    Base.metadata,
    Column("survey_id", Integer, ForeignKey("surveys.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)

class CropFamily(Base):
    __tablename__ = "crop_families"
    id = Column(Integer, primary_key=True, index=True)
    family_name = Column(String(255), nullable=False)
    label = Column(String(255), nullable=True)
    picture = Column(Text, nullable=True)

class NationalCrop(Base):
    __tablename__ = "national_crops"
    id = Column(Integer, primary_key=True, index=True)
    crop_name = Column(String(255), nullable=False)
    crop_id = Column(String(100), nullable=True)
    family_id = Column(Integer, ForeignKey("crop_families.id"))
    picture = Column(Text, nullable=True)
    
    family = relationship("CropFamily")

class Province(Base):
    __tablename__ = "provinces"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    total_customers = Column(Integer, default=0)
    main_crop_family_id = Column(Integer, ForeignKey("crop_families.id"), nullable=True)
    
    main_crop_family = relationship("CropFamily")

class District(Base):
    __tablename__ = "districts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    province_id = Column(Integer, ForeignKey("provinces.id"))
    total_customers = Column(Integer, default=0)
    district_type = Column(String(100), nullable=True)
    main_crop_family_id = Column(Integer, ForeignKey("crop_families.id"), nullable=True)
    
    province = relationship("Province")
    main_crop_family = relationship("CropFamily")

class Region(Base):
    __tablename__ = "regions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id"))
    province_id = Column(Integer, ForeignKey("provinces.id"))
    total_customers = Column(Integer, default=0)
    region_type = Column(String(100), nullable=True)
    main_crop_family_id = Column(Integer, ForeignKey("crop_families.id"), nullable=True)
    is_approved = Column(Boolean, default=False)
    
    district = relationship("District")
    province = relationship("Province")
    main_crop_family = relationship("CropFamily")

class RegionalCrop(Base):
    __tablename__ = "regional_crops"
    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    rcrop_id = Column(String(100), nullable=True) # External or code ID
    crop_name = Column(String(255), nullable=False)
    family_id = Column(Integer, ForeignKey("crop_families.id"))
    picture = Column(Text, nullable=True)
    
    region = relationship("Region")
    family = relationship("CropFamily")

class Camp(Base):
    __tablename__ = "camps"
    id = Column(Integer, primary_key=True, index=True)
    region_id = Column(Integer, ForeignKey("regions.id"))
    province_id = Column(Integer, ForeignKey("provinces.id"))
    district_id = Column(Integer, ForeignKey("districts.id"))
    name = Column(String(255), nullable=False)
    camp_type = Column(String(100), nullable=True)
    total_customers = Column(Integer, default=0)
    
    region = relationship("Region")
    province = relationship("Province")
    district = relationship("District")

class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False) # sms, push
    message = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)

class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)   # who sent it
    type = Column(String(20), nullable=False) # sms, push
    title = Column(String(255), nullable=True)
    message = Column(String, nullable=False)
    icon = Column(String(50), nullable=True)
    status = Column(String(20), default="pending") # sent, read, failed
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean(), default=False)
    
    recipient = relationship("User", back_populates="notifications", foreign_keys=[recipient_id])
    sender   = relationship("User", foreign_keys=[sender_id])

chat_group_members = Table(
    "chat_group_members",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("group_id", Integer, ForeignKey("chat_groups.id"), primary_key=True),
)

class ChatGroup(Base):
    __tablename__ = "chat_groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_type = Column(String(50), nullable=True) # "NATIONAL", "PROVINCIAL", "DISTRICT", "REGION", "CAMP", or "DIRECT"
    province_id = Column(Integer, ForeignKey("provinces.id"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)
    camp_id = Column(Integer, ForeignKey("camps.id"), nullable=True)
    
    members = relationship("User", secondary=chat_group_members, backref="chat_groups")
    messages = relationship("ChatMessage", back_populates="group")
    province = relationship("Province")
    district = relationship("District")
    region = relationship("Region")
    camp = relationship("Camp")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(String, nullable=True) # Text can be null if it's only an image
    media_url = Column(String(500), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    group = relationship("ChatGroup", back_populates="messages")

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)  # Male, Female, Other
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(String, nullable=True)
    cnic = Column(String(20), unique=True, index=True, nullable=True)
    category = Column(String(100), nullable=True) # e.g. Priority, Regular, Area-specific
    survey_data = Column(String, nullable=True) # JSON or serialized data

    # Location hierarchy
    farmer_id = Column(String(50), nullable=True)  # FarmerID
    camp_id = Column(Integer, ForeignKey("camps.id"), nullable=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)
    province_id = Column(Integer, ForeignKey("provinces.id"), nullable=True)
    membership_status = Column(String(50), nullable=True)
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_camp_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Camp user who owns this customer (max 100 per Camp user)
    household = Column(String(255), nullable=True)  # HouseHold
    education_level = Column(String(100), nullable=True)
    emp_status = Column(String(100), nullable=True)  # Employment status
    photo = Column(String(500), nullable=True)  # Photo URL

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class SystemConfiguration(Base):
    __tablename__ = "system_configurations"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, index=True, nullable=False) # e.g., 'sms_settings', 'push_settings'
    value = Column(String, nullable=False) # JSON string
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(255), nullable=False) # e.g., 'UPDATE_AGENT', 'DELETE_REPORT'
    details = Column(String, nullable=True) # JSON or descriptive string
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(50), nullable=True)
    
    user = relationship("User")

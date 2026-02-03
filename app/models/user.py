import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, DateTime, Float, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "System Super Admin"
    ADMINISTRATOR = "System Administrator"
    EXECUTIVE = "Executive User"
    NATIONAL = "National User"
    PROVINCIAL = "Provincial User"
    DISTRICT = "District user"
    REGION = "Region User"
    CAMP = "Camp User"
    AGENT = "Agent"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.AGENT, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    
    # Hierarchy
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    parent = relationship("User", remote_side=[id], backref="subordinates")
    
    # Contact Info
    phone = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Last Known Location for GIS Tracking
    last_lat = Column(Float, nullable=True)
    last_lng = Column(Float, nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    location = Column(String(255), nullable=True) # Assigned area or address

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    reports = relationship("Report", back_populates="agent")
    notifications = relationship("NotificationLog", back_populates="recipient")

class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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

    agent = relationship("User", back_populates="reports")
    images = relationship("ReportImage", back_populates="report", cascade="all, delete-orphan")
    edits = relationship("ReportEditHistory", back_populates="report", cascade="all, delete-orphan")

class ReportImage(Base):
    __tablename__ = "report_images"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    image_url = Column(Text, nullable=False)
    
    report = relationship("Report", back_populates="images")

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

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(Enum(SurveyStatus), default=SurveyStatus.DRAFT)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

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
    type = Column(String(20), nullable=False) # sms, push
    message = Column(String, nullable=False)
    status = Column(String(20), default="pending") # sent, failed, retry
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    recipient = relationship("User", back_populates="notifications")

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
    
    members = relationship("User", secondary=chat_group_members, backref="chat_groups")
    messages = relationship("ChatMessage", back_populates="group")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    group = relationship("ChatGroup", back_populates="messages")

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(String, nullable=True)
    cnic = Column(String(20), unique=True, index=True, nullable=True)
    category = Column(String(100), nullable=True) # e.g. Priority, Regular, Area-specific
    survey_data = Column(String, nullable=True) # JSON or serialized data
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

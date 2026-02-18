from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Text
from app.core.auth import get_current_user, RoleChecker
from app.db.session import get_db
from app.models.user import User, NotificationTemplate, NotificationLog, SystemConfiguration, UserRole
from pydantic import BaseModel
import json

from app.core.audit import log_action

router = APIRouter()

class TemplateCreate(BaseModel):
    name: str
    type: str # sms or push
    message: str
    is_active: bool = True

class NotificationSend(BaseModel):
    type: str
    recipient_type: str = "individual" # individual, allAgents, byRole, byRegion
    recipient_value: Optional[str] = None
    message: str

class ConfigSave(BaseModel):
    key: str # 'sms_settings' or 'push_settings'
    value: dict

@router.get("/templates")
def get_templates(db: Session = Depends(get_db)):
    return db.query(NotificationTemplate).all()

@router.post("/templates")
def create_template(template: TemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_template = NotificationTemplate(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    
    log_action(db, current_user.id, "CREATE_NOTIF_TEMPLATE", f"Created notification template '{template.name}' ({template.type})")
    
    return db_template

@router.get("/logs")
def get_logs(db: Session = Depends(get_db)):
    logs = db.query(NotificationLog).order_by(NotificationLog.timestamp.desc()).all()
    # Format for frontend
    return [
        {
            "id": l.id,
            "recipient": l.recipient.full_name if l.recipient else f"User {l.recipient_id}",
            "type": l.type,
            "message": l.message,
            "status": l.status,
            "created_at": l.timestamp
        }
        for l in logs
    ]

@router.post("/send")
def send_notification(payload: NotificationSend, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target_users = []
    
    if payload.recipient_type == 'individual':
        # Try to find recipient by ID, email or phone
        val = payload.recipient_value
        recipient = db.query(User).filter(
            (User.id.cast(Text) == val) | (User.email == val) | (User.phone == val)
        ).first()
        if recipient:
            target_users.append(recipient)
            
    elif payload.recipient_type == 'allAgents':
        target_users = db.query(User).filter(User.role == "Agent").all()
        
    elif payload.recipient_type == 'byRole':
        target_users = db.query(User).filter(User.role == payload.recipient_value).all()
        
    elif payload.recipient_type == 'byRegion':
        # Search in the 'location' field or a dedicated region field if available
        # For now, searching 'location'
        target_users = db.query(User).filter(User.location.ilike(f"%{payload.recipient_value}%")).all()
    
    if not target_users:
        # Fallback to current user if nothing found for demo purposes
        # target_users = [current_user]
        pass

    logs = []
    for user in target_users:
        log = NotificationLog(
            recipient_id=user.id,
            type=payload.type,
            message=payload.message,
            status="sent"
        )
        db.add(log)
        logs.append(log)
        
    db.commit()
    for log in logs:
        db.refresh(log)
        
    log_action(db, current_user.id, "SEND_NOTIFICATION", f"Sent {len(logs)} {payload.type} notifications. Filter: {payload.recipient_type}")
        
    return {"status": "success", "count": len(logs)}

@router.get("/config/{key}")
def get_config(key: str, db: Session = Depends(get_db)):
    config = db.query(SystemConfiguration).filter(SystemConfiguration.key == key).first()
    if not config:
        return {"key": key, "value": {}}
    return {"key": key, "value": json.loads(config.value)}

@router.post("/config")
def save_config(
    payload: ConfigSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR])),
):
    config = db.query(SystemConfiguration).filter(SystemConfiguration.key == payload.key).first()
    if config:
        config.value = json.dumps(payload.value)
    else:
        config = SystemConfiguration(key=payload.key, value=json.dumps(payload.value))
        db.add(config)
    db.commit()
    
    log_action(db, current_user.id, "UPDATE_CONFIG", f"Updated system configuration for '{payload.key}'")
    
    return {"message": "Configuration saved successfully"}

@router.post("/retry/{log_id}")
def retry_notification(log_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    log = db.query(NotificationLog).filter(NotificationLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    
    # Create new log entry for the retry
    new_log = NotificationLog(
        recipient_id=log.recipient_id,
        type=log.type,
        message=log.message,
        status="sent" # Assuming success for demo
    )
    db.add(new_log)
    
    db.commit()
    db.refresh(new_log)
    
    log_action(db, current_user.id, "RETRY_NOTIFICATION", f"Retried notification {log_id}")
    
    return new_log

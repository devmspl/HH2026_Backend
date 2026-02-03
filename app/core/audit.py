from sqlalchemy.orm import Session
from app.models.user import AuditLog, User
from typing import Optional

def log_action(db: Session, user_id: int, action: str, details: Optional[str] = None, ip_address: Optional[str] = None):
    """
    Log an administrative action.
    """
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=ip_address
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

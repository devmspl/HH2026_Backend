from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.v1.endpoints import login
from app.core.auth import get_current_user, RoleChecker
from app.core.role_permissions import can_create_role, get_creatable_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas import user as user_schema
from app.core.security import get_password_hash
from app.core.audit import log_action

router = APIRouter()

@router.get("/", response_model=List[user_schema.User])
def read_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR, UserRole.EXECUTIVE, UserRole.NATIONAL, UserRole.PROVINCIAL, UserRole.DISTRICT, UserRole.REGION, UserRole.CAMP])),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve agents.
    Hierarchy-based filtering should be applied here in a real scenario.
    """
    # Simple filtering: return only users with role AGENT or based on subordinates logic
    # Debug info
    print(f"DEBUG: Current User Role: {current_user.role} (type: {type(current_user.role)})")
    
    # Robust comparison: Check string value or Enum or is_superuser flag
    is_super = False
    
    # Check 1: Database flag
    if current_user.is_superuser:
        is_super = True
    
    # Check 2: Direct Enum comparison
    elif current_user.role == UserRole.SUPER_ADMIN:
        is_super = True
        
    # Check 3: String value comparison (handling Enum vs String)
    elif str(current_user.role) == "System Super Admin":
        is_super = True
        
    # Check 4: Accessing .value if it's an enum
    elif hasattr(current_user.role, 'value') and current_user.role.value == "System Super Admin":
        is_super = True

    if is_super:
        users = db.query(User).offset(skip).limit(limit).all()
    else:
        # For non-super admins, we typically show subordinates.
        # BUT, to allow assigning YOURSELF as a manager (if you have permission to add users), 
        # you need to see yourself in the list.
        # So we fetch subordinates OR the user themselves.
        users = db.query(User).filter((User.parent_id == current_user.id) | (User.id == current_user.id)).all()
        
    return users

@router.post("/", response_model=user_schema.User)
def create_agent(
    *,
    db: Session = Depends(get_db),
    agent_in: user_schema.UserCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create new agent with role-based access control.
    """
    # Check if current user can create the requested role
    if not can_create_role(current_user.role, agent_in.role):
        creatable_roles = get_creatable_roles(current_user.role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have permission to create users with role '{agent_in.role}'. "
                   f"You can only create: {[role.value for role in creatable_roles]}"
        )
    
    user = db.query(User).filter(User.email == agent_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    db_obj = User(
        email=agent_in.email,
        hashed_password=get_password_hash(agent_in.password),
        full_name=agent_in.full_name,
        role=agent_in.role,
        parent_id=agent_in.parent_id if agent_in.parent_id else current_user.id,
        is_active=True,
        last_lat=agent_in.last_lat,
        last_lng=agent_in.last_lng,
        location=agent_in.location,
        phone=agent_in.phone,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    log_action(db, current_user.id, "CREATE_USER", f"Created user {db_obj.full_name} ({db_obj.role})")
    
    return db_obj

@router.get("/creatable-roles")
def get_creatable_roles_endpoint(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get list of roles that the current user can create.
    """
    creatable_roles = get_creatable_roles(current_user.role)
    return {
        "user_role": current_user.role.value,
        "creatable_roles": [role.value for role in creatable_roles]
    }

@router.put("/{agent_id}", response_model=user_schema.User)
def update_agent(
    *,
    db: Session = Depends(get_db),
    agent_id: int,
    agent_in: user_schema.UserUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update an agent with role-based access control.
    """
    agent = db.query(User).filter(User.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    update_data = agent_in.dict(exclude_unset=True)
    
    # Role validation - check if user can change the role
    if "role" in update_data:
        new_role = update_data["role"]
        
        # Check if current user can assign this role
        if not can_create_role(current_user.role, new_role):
            creatable_roles = get_creatable_roles(current_user.role)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to change role to '{new_role}'. "
                       f"You can only assign: {[role.value for role in creatable_roles]}"
            )
        
        # Additional check: prevent users from modifying roles of users at or above their level
        if get_role_hierarchy_level(agent.role) >= get_role_hierarchy_level(current_user.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot modify users at or above your privilege level."
            )
    
    # Status validation - prevent deactivating Super Admins
    if "is_active" in update_data and not update_data["is_active"]:
        if agent.role == UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot deactivate Super Admin users for system security."
            )
    
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data["password"])
        del update_data["password"]
    
    for field in update_data:
        setattr(agent, field, update_data[field])
    
    db.commit()
    db.refresh(agent)
    
    log_action(db, current_user.id, "UPDATE_USER", f"Updated user {agent.full_name}. Data: {update_data}")
    
    return agent

@router.get("/{agent_id}/logs")
def get_agent_logs(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get activity logs for an agent.
    """
    from app.models.user import Report, ReportEditHistory
    
    # Recent reports
    reports = db.query(Report).filter(Report.agent_id == agent_id).order_by(Report.created_at.desc()).limit(10).all()
    
    logs = [
        {
            "id": r.id,
            "type": "report_submission",
            "message": f"Submitted report: {r.title}",
            "time": r.created_at
        }
        for r in reports
    ]
    
    # Recent edits
    edits = db.query(ReportEditHistory).filter(ReportEditHistory.user_id == agent_id).order_by(ReportEditHistory.timestamp.desc()).limit(10).all()
    logs += [
        {
            "id": e.id,
            "type": "report_edit",
            "message": f"Edited report: {e.changes}",
            "time": e.timestamp
        }
        for e in edits
    ]
    
    # Sort by time
    logs.sort(key=lambda x: x["time"], reverse=True)
    return logs[:20]

@router.delete("/{agent_id}")
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR])),
):
    """
    Delete an agent.
    """
    agent = db.query(User).filter(User.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Prevent deletion of Super Admins
    if agent.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete Super Admin users for system security."
        )
    
    agent_name = agent.full_name
    
    try:
        # Delete related records first to avoid foreign key constraints
        from app.models.user import NotificationLog, Report, ReportEditHistory, ChatMessage, ReportImage, AuditLog
        
        # Delete notification logs
        db.query(NotificationLog).filter(NotificationLog.recipient_id == agent_id).delete()
        
        # Delete chat messages (sender_id instead of user_id)
        db.query(ChatMessage).filter(ChatMessage.sender_id == agent_id).delete()
        
        # Get agent's reports to delete related records first
        agent_reports = db.query(Report).filter(Report.agent_id == agent_id).all()
        
        # Delete report images for each report
        for report in agent_reports:
            db.query(ReportImage).filter(ReportImage.report_id == report.id).delete()
        
        # Delete report edit history for each report (before deleting reports)
        for report in agent_reports:
            db.query(ReportEditHistory).filter(ReportEditHistory.report_id == report.id).delete()
        
        # Delete reports (after images and edit history are deleted)
        db.query(Report).filter(Report.agent_id == agent_id).delete()
        
        # Delete any remaining report edit history by user_id
        db.query(ReportEditHistory).filter(ReportEditHistory.user_id == agent_id).delete()
        
        # Delete audit logs for this user
        db.query(AuditLog).filter(AuditLog.user_id == agent_id).delete()
        
        # Finally delete the agent
        db.delete(agent)
        db.commit()
        
        return {"message": "Agent deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")

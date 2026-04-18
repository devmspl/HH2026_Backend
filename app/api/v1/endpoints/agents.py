import secrets
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.v1.endpoints import login
from app.core.auth import get_current_user, RoleChecker
from app.core.role_permissions import can_create_role, get_creatable_roles
from app.db.session import get_db
from app.models.user import User, UserRole, AccountStatus
from app.schemas import user as user_schema
from app.core.security import get_password_hash
from app.core.audit import log_action

router = APIRouter()

from app.core.role_permissions import ROLE_HIERARCHY

def get_role_level(role: Any) -> int:
    if not role:
        return 0
    # Try direct match (handles UserRole enum and exact strings like "SUPER_ADMIN")
    if role in ROLE_HIERARCHY:
        return ROLE_HIERARCHY[role]
    # Try case-insensitive string match
    role_str = str(role).upper()
    if role_str in ROLE_HIERARCHY:
        return ROLE_HIERARCHY[role_str]
    # Fallback to 0 (lowest)
    return 0


@router.get("/", response_model=List[user_schema.User])
def read_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    role: Optional[str] = None,
) -> Any:
    """
    Retrieve agents based on role hierarchy and optional role filter.
    """
    current_level = get_role_level(current_user.role)
    
    # Base query
    query = db.query(User)
    
    # Filter by specific role if provided
    if role:
        role_upper = role.upper()
        query = query.filter(func.upper(User.role).in_([role_upper, role_upper.title(), role_upper.upper(), role_upper.lower()]))
    
    # Filter by status if provided
    if status:
        query = query.filter(User.account_status == status)
        
    # Exclude deleted by default in main list
    query = query.filter(User.is_deleted == False)
    
    # Hierarchy filtering logic
    is_admin = current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR, UserRole.EXECUTIVE]
    
    if is_admin:
        # Senior roles see all roles (National Scope)
        from app.models.user import SystemRole
        allowed_roles = list(ROLE_HIERARCHY.keys())
        allowed_role_strs = [r.value if hasattr(r, 'value') else str(r) for r in allowed_roles]
        
        # Also include any custom system roles if their mapped level (default 0) <= current_level
        system_roles = db.query(SystemRole).all()
        for sr in system_roles:
            if get_role_level(sr.name) <= current_level:
                allowed_role_strs.append(sr.name)
                # also append title case or upper case as fallback
                allowed_role_strs.append(sr.name.upper())
                allowed_role_strs.append(sr.name.title())
                
        # Also add capitalized standard roles just in case
        for r in allowed_roles:
            val = r.value if hasattr(r, 'value') else str(r)
            allowed_role_strs.append(val.title())
            allowed_role_strs.append(val.upper())

        # Filter by string match
        query = query.filter(User.role.in_(allowed_role_strs))
        
        # Exclude SUPER_ADMIN from the visible list for everyone EXCEPT SUPER_ADMIN
        if str(current_user.role).upper() not in ["SUPER_ADMIN", "SUPER_ADMIN", "SUPER_ADMIN"]:
            query = query.filter(
                User.role != UserRole.SUPER_ADMIN.value,
                User.role != "SUPER_ADMIN",
                User.role != "Super_Admin" # case safety
            )
    else:
        # Non-admins only see their recursive subordinates
        to_process = [current_user.id]
        sub_ids = []
        processed = {current_user.id}
        
        while to_process:
            pid = to_process.pop()
            subs = db.query(User.id).filter(User.parent_id == pid, User.is_deleted == False).all()
            for s in subs:
                sid = s[0]
                if sid not in processed:
                    sub_ids.append(sid)
                    to_process.append(sid)
                    processed.add(sid)
                    
        # --- Geographic Visibility Overrides ---
        r = str(current_user.role).upper()
        extra_users = []
        if r == "NATIONAL":
            extra_users = db.query(User.id).filter(
                User.role.in_(["NATIONAL", "National", "PROVINCIAL", "Provincial", "DISTRICT", "District"]),
                User.is_deleted == False
            ).all()
        elif r == "PROVINCIAL" and current_user.province_id:
            extra_users = db.query(User.id).filter(
                User.province_id == current_user.province_id,
                User.role.in_(["PROVINCIAL", "Provincial", "DISTRICT", "District", "REGION", "Region", "CAMP", "Camp", "AGENT", "Agent"]),
                User.is_deleted == False
            ).all()
        elif r == "DISTRICT" and current_user.district_id:
            extra_users = db.query(User.id).filter(
                User.district_id == current_user.district_id,
                User.role.in_(["DISTRICT", "District", "REGION", "Region", "CAMP", "Camp", "AGENT", "Agent"]),
                User.is_deleted == False
            ).all()
        elif r == "REGION" and current_user.region_id:
            extra_users = db.query(User.id).filter(
                User.region_id == current_user.region_id,
                User.role.in_(["REGION", "Region", "CAMP", "Camp", "AGENT", "Agent"]),
                User.is_deleted == False
            ).all()
        elif r == "CAMP" and current_user.region_id:
            extra_users = db.query(User.id).filter(
                User.region_id == current_user.region_id,
                User.role.in_(["REGION", "Region", "CAMP", "Camp", "AGENT", "Agent"]),
                User.is_deleted == False
            ).all()
        elif r == "AGENT" and current_user.region_id:
            extra_users = db.query(User.id).filter(
                User.region_id == current_user.region_id,
                User.role.in_(["REGION", "Region", "CAMP", "Camp", "AGENT", "Agent"]), # Included fellow agents for standard access
                User.is_deleted == False
            ).all()
            
        for eu in extra_users:
            if eu[0] not in sub_ids:
                sub_ids.append(eu[0])
        # ----------------------------------------
        
        if not sub_ids:
            return [] # No subordinates
            
        query = query.filter(User.id.in_(sub_ids))
    
    # 3. Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    # 4. Attach approver details for each user
    result = []
    for user in users:
        user_dict = user_schema.User.model_validate(user).model_dump()
        
        # Fetch approver details if approved_by exists
        if user.approved_by:
            approver = db.query(User).filter(User.id == user.approved_by).first()
            if approver:
                user_dict['approver_details'] = {
                    'id': approver.id,
                    'full_name': approver.full_name,
                    'role': approver.role.value if hasattr(approver.role, 'value') else str(approver.role) if approver.role else None,
                    'avatar_url': approver.avatar_url
                }
        
        result.append(user_dict)
        
    return result

@router.get("/approval-list", response_model=List[user_schema.User])
def get_approval_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get list of users waiting for approval.
    Show pending users whose role is just below or equal to the current user (depending on who needs to approve).
    Logic: Higher role approves lower role's self-creation.
    If 'Executive' creates 'Executive', 'System Admin' approves.
    So 'System Admin' looks for 'Pending' users with role 'Executive'.
    """
    current_level = get_role_level(current_user.role)
    
    # We look for users who are PENDING and have a role that this user is authorized to approve.
    # Typically, you approve users immediately below you who were created by someone of their own rank.
    # For simplicity/broadness: Show ALL pending users that are strictly LOWER than current user.
    
    allowed_roles = [role for role, level in ROLE_HIERARCHY.items() if level < current_level]
    allowed_role_strs = [r.value if hasattr(r, 'value') else str(r) for r in allowed_roles]
    
    from app.models.user import SystemRole
    system_roles = db.query(SystemRole).all()
    for sr in system_roles:
        if get_role_level(sr.name) < current_level:
            allowed_role_strs.append(sr.name)
            allowed_role_strs.append(sr.name.upper())
            allowed_role_strs.append(sr.name.title())

    for r in allowed_roles:
        val = r.value if hasattr(r, 'value') else str(r)
        allowed_role_strs.append(val.title())
        allowed_role_strs.append(val.upper())

    users = db.query(User).filter(
        User.account_status == AccountStatus.PENDING,
        User.role.in_(allowed_role_strs)
    ).all()
    
    return users

@router.post("/{agent_id}/approve", response_model=user_schema.User)
def approve_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Approve a pending agent.
    """
    agent = db.query(User).filter(User.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    if agent.account_status != AccountStatus.PENDING:
        raise HTTPException(status_code=400, detail="User is not pending approval")
        
    # Check hierarchy
    if get_role_level(current_user.role) <= get_role_level(agent.role):
        raise HTTPException(status_code=403, detail="You cannot approve users with equal or higher rank")
        
    agent.account_status = AccountStatus.ACTIVE
    agent.is_active = True
    agent.approved_by = current_user.id
    from datetime import datetime
    agent.approved_at = datetime.now()
    db.commit()
    db.refresh(agent)
    
    log_action(db, current_user.id, "APPROVE_USER", f"Approved user {agent.full_name} ({agent.role})")
    return agent

@router.post("/{agent_id}/reject", response_model=user_schema.User)
def reject_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Reject a pending agent.
    """
    agent = db.query(User).filter(User.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent.account_status != AccountStatus.PENDING:
        raise HTTPException(status_code=400, detail="User is not pending approval")

    # Check hierarchy
    if get_role_level(current_user.role) <= get_role_level(agent.role):
        raise HTTPException(status_code=403, detail="You cannot reject users with equal or higher rank")
        
    agent.account_status = AccountStatus.REJECTED
    agent.is_active = False # Ensure they can't login
    db.commit()
    db.refresh(agent)
    
    log_action(db, current_user.id, "REJECT_USER", f"Rejected user {agent.full_name} ({agent.role})")
    return agent


@router.post("/", response_model=user_schema.User)
def create_agent(
    *,
    db: Session = Depends(get_db),
    agent_in: user_schema.UserCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create new agent with role-based access control and approval workflow.
    """
    current_level = get_role_level(current_user.role)
    new_role_level = get_role_level(agent_in.role)

    # 1. Validation: Cannot create higher rank
    if new_role_level > current_level:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot create a user with a higher role than yourself."
        )
    
    user = db.query(User).filter(User.email == agent_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
        
    # 2. Determine Status
    # If same role created -> Pending Approval
    # If lower role created -> Active
    account_status = AccountStatus.ACTIVE
    is_active = True
    
    if new_role_level == current_level:
        # If Super Admin creates Super Admin, they are effectively the highest authority, so maybe auto-approve?
        # But generally, prompt says "same role user... has to approval from there higher role".
        # If System Super Admin creates System Super Admin, there is no higher role. 
        # Assume Super Admin creation is always instant or handled specially?
        # Let's exempt Super Admin from this check or assume it's fine.
        if current_user.role != UserRole.SUPER_ADMIN:
            account_status = AccountStatus.PENDING
            is_active = False # Inactive until approved
        
    user_role = agent_in.role
    # If a dynamic role_id is provided, sync the role name from the SystemRole table
    if agent_in.role_id:
        from app.models.user import SystemRole
        system_role = db.query(SystemRole).filter(SystemRole.id == agent_in.role_id).first()
        if system_role:
            user_role = system_role.name

    db_obj = User(
        email=agent_in.email,
        hashed_password=get_password_hash(agent_in.password),
        full_name=agent_in.full_name,
        role=user_role,
        parent_id=agent_in.parent_id if agent_in.parent_id else current_user.id,
        is_active=is_active,
        account_status=account_status,
        last_lat=agent_in.last_lat,
        last_lng=agent_in.last_lng,
        location=agent_in.location,
        phone=agent_in.phone,
        permissions=agent_in.permissions,
        role_id=agent_in.role_id,
        age=agent_in.age,
        sex=agent_in.sex,
        profession=agent_in.profession,
        nrc=agent_in.nrc,
        province_id=agent_in.province_id,
        district_id=agent_in.district_id,
        region_id=agent_in.region_id,
        camp_id=agent_in.camp_id,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    
    log_action(db, current_user.id, "CREATE_USER", f"Created user {db_obj.full_name} ({db_obj.role}). Status: {account_status}")
    
    # Auto-assign to groups
    from app.services.chat_service import sync_user_groups
    sync_user_groups(db, db_obj)
    
    return db_obj

@router.get("/creatable-roles")
def get_creatable_roles_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get list of roles that the current user can create.
    """
    from app.models.user import SystemRole
    current_level = get_role_level(current_user.role)
    # User can create roles <= their own level
    creatable = [role.value for role, level in ROLE_HIERARCHY.items() if level <= current_level]
    
    # Get dynamic roles
    system_roles = db.query(SystemRole).all()
    
    display_role = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    
    return {
        "user_role": display_role,
        "creatable_roles": [r.value if hasattr(r, 'value') else str(r) for r in creatable],
        "system_roles": [
            {"id": sr.id, "name": sr.name, "permissions": sr.permissions} 
            for sr in system_roles
        ]
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
    
    current_level = get_role_level(current_user.role)
    agent_level = get_role_level(agent.role)
    
    # Permission Check: Can only edit users with Equal or Lower level
    if current_level < agent_level:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot update a user with a higher role than yourself."
        )
         
    # If editing SAME level user, restrict what can be done? 
    # Usually you can't edit your peer's profile unless you are admin.
    # Prompt says "hr user ko bs as user ka asses rhega... system administrator: (..., agent)"
    # This implies System Admin can edit System Admin?
    # Usually editing yourself is fine. Editing other System Admin might typically be allowed.
    # Restricting editing of OTHER peers might be safer, but adhering to "Access" rule:
    # If I see them, I can edit them.
    
    update_data = agent_in.dict(exclude_unset=True)
    
    # Role validation - check if user can change the role
    if "role" in update_data:
        new_role = update_data["role"]
        new_role_level = get_role_level(new_role)
        
        if new_role_level >= current_level and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You cannot assign a role equal to or higher than your own."
            )

    # Sync role string if role_id is updated
    if "role_id" in update_data and update_data["role_id"]:
        from app.models.user import SystemRole
        system_role = db.query(SystemRole).filter(SystemRole.id == update_data["role_id"]).first()
        if system_role:
            update_data["role"] = system_role.name
            
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
    
    # Sync groups in case of role/location change
    from app.services.chat_service import sync_user_groups
    sync_user_groups(db, agent)
    
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


@router.post("/{agent_id}/reset-password")
def reset_agent_password(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Generate a new random password for the user and return it (plain).
    Only SUPER_ADMIN can call this. Use it to set/send password to the user.
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can reset user passwords.",
        )
    agent = db.query(User).filter(User.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="User not found")
    # Generate a random password (e.g. 12 chars, letters + digits)
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    plain_password = "".join(secrets.choice(alphabet) for _ in range(12))
    agent.hashed_password = get_password_hash(plain_password)
    db.commit()
    log_action(db, current_user.id, "RESET_PASSWORD", f"Password reset for user {agent.full_name} (id={agent_id})")
    return {"password": plain_password}


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete an agent.
    """
    agent = db.query(User).filter(User.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    current_level = get_role_level(current_user.role)
    agent_level = get_role_level(agent.role)

    # Permission Check
    if current_level <= agent_level:
        raise HTTPException(status_code=403, detail="You cannot delete a user with equal or higher rank than yourself")
        
    # Prevent deletion of Super Admins
    if agent.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete Super Admin users for system security."
        )
    
    agent_name = agent.full_name
    
    try:
        # Soft Delete
        from datetime import datetime
        agent.is_deleted = True
        agent.deleted_at = datetime.now()
        agent.is_active = False # Disable login
        
        db.commit()
        db.refresh(agent)
        
        log_action(db, current_user.id, "DELETE_USER", f"Soft deleted user {agent_name} ({agent.role})")
        
        return {"message": "Agent deleted successfully (Soft Delete)"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")

@router.get("/deleted", response_model=List[user_schema.User])
def read_deleted_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve deleted agents based on role hierarchy.
    """
    current_level = get_role_level(current_user.role)
    
    # Base query
    query = db.query(User).filter(User.is_deleted == True)
    
    # Hierarchy filtering logic
    is_admin = current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]
    
    if is_admin:
        allowed_roles = [role for role, level in ROLE_HIERARCHY.items() if level <= current_level]
        query = query.filter(User.role.in_(allowed_roles))
        query = query.filter(User.role != UserRole.SUPER_ADMIN)
    else:
        # Check recursive subordinates for non-admins
        to_process = [current_user.id]
        sub_ids = []
        processed = {current_user.id}
        while to_process:
            pid = to_process.pop()
            # Note: We check subordinates even if they are NOT deleted yet to find their deleted children, 
            # but actually parent-child links might be broken if parent is deleted? 
            # Standard logic: show anyone who was created by me/my team.
            subs = db.query(User.id).filter(User.parent_id == pid).all()
            for s in subs:
                sid = s[0]
                if sid not in processed:
                    sub_ids.append(sid)
                    to_process.append(sid)
                    processed.add(sid)
        
        if not sub_ids:
            return []
        query = query.filter(User.id.in_(sub_ids))
    
    users = query.offset(skip).limit(limit).all()
        
    return users

@router.post("/{agent_id}/recover", response_model=user_schema.User)
def recover_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Recover a soft-deleted agent.
    """
    agent = db.query(User).filter(User.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    if not agent.is_deleted:
        raise HTTPException(status_code=400, detail="User is not deleted")

    current_level = get_role_level(current_user.role)
    agent_level = get_role_level(agent.role)

    # Permission Check
    if current_level <= agent_level:
        raise HTTPException(status_code=403, detail="You cannot recover a user with equal or higher rank than yourself")
        
    agent.is_deleted = False
    agent.deleted_at = None
    agent.is_active = True # Re-enable login? Or status dependent? 
    # If account_status was active, is_active should be True. 
    # If account_status was pending, maybe they shouldn't be active?
    # For now, let's restore is_active based on account_status.
    if agent.account_status == AccountStatus.ACTIVE:
        agent.is_active = True
    elif agent.account_status == AccountStatus.PENDING:
        agent.is_active = False
    
    db.commit()
    db.refresh(agent)
    
    log_action(db, current_user.id, "RECOVER_USER", f"Recovered user {agent.full_name} ({agent.role})")
    
    return agent


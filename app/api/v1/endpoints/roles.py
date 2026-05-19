from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, SystemRole
from app.schemas.role import Role, RoleCreate, RoleUpdate
from app.core.audit import log_action

router = APIRouter()

@router.get("/", response_model=List[Role])
def get_roles(
    sort_by: str = None,
    sort_order: str = "asc",
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    roles = db.query(SystemRole).all()
    if sort_by:
        is_desc = sort_order.lower() == "desc"
        if sort_by == "RoleName":
            roles.sort(key=lambda r: (r.name or "").lower(), reverse=is_desc)
        elif sort_by == "PermissionsCount":
            import json
            def get_perms_count(r):
                try:
                    return len(json.loads(r.permissions or "[]"))
                except:
                    return 0
            roles.sort(key=get_perms_count, reverse=is_desc)
        elif sort_by == "CreatedAt":
            roles.sort(key=lambda r: r.created_at.isoformat() if r.created_at else "", reverse=is_desc)
    return roles

@router.post("/", response_model=Role)
def create_role(role_in: RoleCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_role = db.query(SystemRole).filter(SystemRole.name == role_in.name).first()
    if db_role:
        raise HTTPException(status_code=400, detail="Role already exists")
    
    db_role = SystemRole(**role_in.dict())
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    
    log_action(db, current_user.id, "CREATE_ROLE", f"Created system role '{db_role.name}'")
    return db_role

@router.put("/{role_id}", response_model=Role)
def update_role(role_id: int, role_in: RoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_role = db.query(SystemRole).filter(SystemRole.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    update_data = role_in.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_role, field, value)
    
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    
    log_action(db, current_user.id, "UPDATE_ROLE", f"Updated system role '{db_role.name}'")
    return db_role

@router.delete("/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_role = db.query(SystemRole).filter(SystemRole.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if users are assigned to this role
    from app.models.user import User as UserTable
    assigned_users = db.query(UserTable).filter(UserTable.role_id == role_id).count()
    if assigned_users > 0:
        raise HTTPException(status_code=400, detail="Cannot delete role with assigned users")
        
    db.delete(db_role)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_ROLE", f"Deleted system role '{db_role.name}'")
    return {"message": "Role deleted"}

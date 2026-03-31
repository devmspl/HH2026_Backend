from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, ChatGroup, ChatMessage, UserRole
from app.schemas import general as general_schema
from pydantic import BaseModel

router = APIRouter()

class MessageCreate(BaseModel):
    chat_group_id: int
    text: str

class GroupCreate(BaseModel):
    name: str
    member_ids: List[int]

from sqlalchemy import text, func

ELIGIBLE_REGION_ROLES = ["REGION", "Region", "region", "CAMP", "Camp", "camp", "AGENT", "Agent", "agent"]

@router.get("/groups", response_model=List[general_schema.ChatGroup])
def get_chat_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Super admins see everything, others see groups they are members of
    if current_user.is_superuser:
        return db.query(ChatGroup).all()
    return current_user.chat_groups

@router.get("/fix-db")
def fix_database_errors(db: Session = Depends(get_db)):
    msgs = []
    try:
        db.execute(text("ALTER TABLE chat_groups ADD COLUMN group_type VARCHAR(50);"))
        db.commit()
        msgs.append("Added group_type to chat_groups")
    except Exception as e:
        db.rollback()
        msgs.append(f"group_type error: {e}")
        
    try:
        db.execute(text("ALTER TABLE chat_groups ADD COLUMN region_id INTEGER REFERENCES regions(id);"))
        db.commit()
        msgs.append("Added region_id to chat_groups")
    except Exception as e:
        db.rollback()
        msgs.append(f"region_id error: {e}")
        
    try:
        db.execute(text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(50) USING role::text;"))
        db.commit()
        msgs.append("Altered role to VARCHAR(50)")
    except Exception as e:
        db.rollback()
        msgs.append(f"role error: {e}")
        
    return {"status": "Complete", "logs": msgs}

@router.post("/groups", response_model=general_schema.ChatGroup)
def create_chat_group(payload: GroupCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 1. Determine if this is a Direct Chat (1:1) vs a Group Chat
    # Direct chat has only 1 other member in member_ids
    is_direct_chat = len(payload.member_ids or []) == 1
    
    # 2. Apply permissions: Only Admin can create Groups (3+ members). Anyone can create Direct (2 members).
    if not is_direct_chat:
        if not current_user.is_superuser and current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
            raise HTTPException(status_code=403, detail="Only Administrators can create multi-member chat groups")

    db_group = ChatGroup(name=payload.name, manager_id=current_user.id)
    
    # Add members
    member_ids = set(payload.member_ids or [])
    member_ids.add(current_user.id) # Always add creator
    members = db.query(User).filter(User.id.in_(list(member_ids))).all()
    db_group.members = members
    
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

@router.post("/groups/auto-create")
def auto_create_hierarchical_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Automatically create or update chat groups for every manager and their subordinates, 
    and system-wide geographic groups (National, Provincial, District, Regional, Camp).
    """
    from app.services.chat_service import sync_all_groups
    created_count = 0
    updated_count = 0
    
    # 1. Team Groups (Manager + Subordinates)
    managers = db.query(User).filter(User.subordinates.any()).all()
    for manager in managers:
        group_name = f"{manager.full_name}'s Team"
        existing_group = db.query(ChatGroup).filter(
            ChatGroup.manager_id == manager.id,
            ChatGroup.name == group_name
        ).first()
        
        current_members = [manager] + manager.subordinates
        if not existing_group:
            new_group = ChatGroup(name=group_name, manager_id=manager.id)
            new_group.members = current_members
            db.add(new_group)
            created_count += 1
        else:
            existing_group.members = current_members
            updated_count += 1
            
    # 2. System-wide Geographic/Role Groups (National, province, district, region, camp)
    s_created, s_updated = sync_all_groups(db)
    
    created_count += s_created
    updated_count += s_updated

    return {
        "message": f"Auto-sync complete: Created {created_count} groups, Updated {updated_count} groups.", 
        "created": created_count,
        "updated": updated_count
    }

@router.post("/groups/{group_id}/members/{user_id}")
def add_member(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(ChatGroup).filter(ChatGroup.id == group_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    if not group or not user:
        raise HTTPException(status_code=404, detail="Group or User not found")
    
    if user not in group.members:
        group.members.append(user)
        db.commit()
    return {"message": "Member added"}

@router.delete("/groups/{group_id}/members/{user_id}")
def remove_member(group_id: int, user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(ChatGroup).filter(ChatGroup.id == group_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    if not group or not user:
        raise HTTPException(status_code=404, detail="Group or User not found")
    
    if user in group.members:
        group.members.remove(user)
        db.commit()
    return {"message": "Member removed"}

@router.delete("/groups/{group_id}")
def delete_chat_group(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(ChatGroup).filter(ChatGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.manager_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db.query(ChatMessage).filter(ChatMessage.group_id == group_id).delete()
    db.delete(group)
    db.commit()
    return {"message": "Group deleted"}

@router.put("/groups/{group_id}", response_model=general_schema.ChatGroup)
def update_chat_group(group_id: int, payload: GroupCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    group = db.query(ChatGroup).filter(ChatGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Only Admin/SuperAdmin or the group manager can update groups
    if not current_user.is_superuser and current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR] and group.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    group.name = payload.name
    
    # Update members
    member_ids = set(payload.member_ids or [])
    member_ids.add(group.manager_id)
    members = db.query(User).filter(User.id.in_(list(member_ids))).all()
    group.members = members
    
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.get("/messages/{group_id}", response_model=List[general_schema.ChatMessage])
def get_chat_messages(group_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    messages = db.query(ChatMessage).filter(ChatMessage.group_id == group_id).order_by(ChatMessage.timestamp.asc()).all()
    # Add sender_name manually since it's not in the model but in the schema
    for m in messages:
        sender = db.query(User).filter(User.id == m.sender_id).first()
        if sender:
            m.sender_name = sender.full_name
    return messages

@router.post("/send", response_model=general_schema.ChatMessage)
def send_chat_message(payload: MessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    msg = ChatMessage(
        group_id=payload.chat_group_id,
        sender_id=current_user.id,
        text=payload.text
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg

@router.get("/region-members", response_model=List[general_schema.RegionMember])
def get_region_members(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns all users belonging to the same region as the logged-in user.
    """
    if not current_user.region_id:
        return []

    users = db.query(User).filter(
        User.region_id == current_user.region_id,
        User.role.in_(ELIGIBLE_REGION_ROLES),
        User.is_deleted == False
    ).all()
    
    return [{"id": u.id, "name": u.full_name, "role": u.role, "region_id": u.region_id} for u in users]

ELIGIBLE_DISTRICT_ROLES = ["REGION", "Region", "region", "CAMP", "Camp", "camp", "Agent", "AGENT", "agent"]
ELIGIBLE_PROVINCIAL_ROLES = ["DISTRICT", "District", "district", "District User", "DISTRICT USER"]

@router.get("/district-members", response_model=List[general_schema.RegionMember])
def get_district_members(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns all regional and camp users belonging to the same district as the logged-in user.
    """
    if not current_user.district_id:
        return []

    users = db.query(User).filter(
        User.district_id == current_user.district_id,
        User.role.in_(ELIGIBLE_DISTRICT_ROLES),
        User.is_deleted == False
    ).all()
    
    return [{"id": u.id, "name": u.full_name, "role": u.role, "region_id": u.region_id, "district_id": u.district_id} for u in users]

@router.get("/provincial-members", response_model=List[general_schema.RegionMember])
def get_provincial_members(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns all district users (accessible by Provincial users).
    """
    # Note: Provincial users can see all District users in the system or same province 
    # The requirement says "See all users where: role === 'district'"
    
    users = db.query(User).filter(
        User.role.in_(ELIGIBLE_PROVINCIAL_ROLES),
        User.is_deleted == False
    ).all()
    
    return [{"id": u.id, "name": u.full_name, "role": u.role, "region_id": u.region_id, "district_id": u.district_id, "province_id": u.province_id} for u in users]

@router.post("/region-group", response_model=general_schema.RegionGroupResponse)
def create_region_group(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Create or get a Region Chat Group for the current user's region.
    """
    if not current_user.region_id:
        raise HTTPException(status_code=400, detail="User has no assigned region")
    
    # 1. Check if group exists
    from app.models.user import Region
    region = db.query(Region).filter(Region.id == current_user.region_id).first()
    region_name = region.name if region else "Unknown"
    
    group = db.query(ChatGroup).filter(
        ChatGroup.group_type == "REGION",
        ChatGroup.region_id == current_user.region_id
    ).first()
    
    if not group:
        # 2. Create group
        group = ChatGroup(
            name=f"Region - {region_name}",
            manager_id=current_user.id,
            group_type="REGION",
            region_id=current_user.region_id
        )
        db.add(group)
        db.flush() # Get ID
    
    # 3. sync members
    members = db.query(User).filter(
        User.region_id == current_user.region_id,
        User.role.in_(ELIGIBLE_REGION_ROLES),
        User.is_deleted == False
    ).all()
    
    group.members = members
    db.commit()
    db.refresh(group)
    
    return {
        "group_id": group.id,
        "group_name": group.name,
        "members": [{"id": m.id, "name": m.full_name, "role": m.role, "region_id": m.region_id} for m in group.members]
    }

@router.get("/region-group", response_model=general_schema.RegionGroupResponse)
def get_region_group(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch the Region Chat Group details for the current user's region.
    """
    if not current_user.region_id:
        raise HTTPException(status_code=400, detail="User has no assigned region")
    
    group = db.query(ChatGroup).filter(
        ChatGroup.group_type == "REGION",
        ChatGroup.region_id == current_user.region_id
    ).first()
    
    if not group:
        raise HTTPException(status_code=404, detail="Region group not found. Call POST /region-group first.")
    
    return {
        "group_id": group.id,
        "group_name": group.name,
        "members": [{"id": m.id, "name": m.full_name, "role": m.role, "region_id": m.region_id} for m in group.members]
    }

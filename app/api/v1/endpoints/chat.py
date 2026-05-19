from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, ChatGroup, ChatMessage, UserRole
from app.schemas import general as general_schema
from pydantic import BaseModel

router = APIRouter()

class MessageCreate(BaseModel):
    chat_group_id: int
    text: Optional[str] = None
    media_url: Optional[str] = None

class GroupCreate(BaseModel):
    name: str
    member_ids: List[int]

from sqlalchemy import text, func

ELIGIBLE_REGION_ROLES = ["REGION", "Region", "region", "CAMP", "Camp", "camp", "AGENT", "Agent", "agent"]

@router.get("/groups")
def get_chat_groups(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    group_type: Optional[str] = None,
    province_id: Optional[int] = None,
    district_id: Optional[int] = None,
    region_id: Optional[int] = None,
    camp_id: Optional[int] = None,
    search: Optional[str] = None
):
    print(f"[DEBUG CHAT] get_chat_groups called by user: {current_user.id} ({current_user.role})")
    # Super admins see everything, others see groups they are members of
    # Super admins see everything with pagination and filtering
    if current_user.is_superuser:
        query = db.query(ChatGroup)
        if group_type:
            query = query.filter(ChatGroup.group_type == group_type)
        if province_id:
            query = query.filter(ChatGroup.province_id == province_id)
        if district_id:
            query = query.filter(ChatGroup.district_id == district_id)
        if region_id:
            query = query.filter(ChatGroup.region_id == region_id)
        if camp_id:
            query = query.filter(ChatGroup.camp_id == camp_id)
        if search:
            query = query.filter(ChatGroup.name.ilike(f"%{search}%"))
            
        total = query.count()
        groups = query.offset((page - 1) * limit).limit(limit).all()
        with open("chat_debug.log", "a") as f:
            f.write(f"\n[DEBUG CHAT] Super Admin - Page {page}, Limit {limit}, Found {len(groups)} groups for type {group_type}\n")
            if groups:
                f.write(f"[DEBUG CHAT] Sample group type: {groups[0].group_type}\n")
        
        items = []
        for g in groups:
            items.append({
                "id": g.id,
                "name": g.name,
                "group_type": g.group_type,
                "manager_id": g.manager_id,
                "province_id": g.province_id,
                "district_id": g.district_id,
                "region_id": g.region_id,
                "camp_id": g.camp_id,
                "members": [{"id": m.id, "full_name": m.full_name, "role": m.role} for m in g.members]
            })
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
    
    # FOR OTHER ROLES: Maintain current behavior but wrap in same structure for consistency
    user_role = str(current_user.role).upper()
    
    if user_role in ["AGENT", "CAMP"]:
        from app.services.chat_service import sync_user_groups
        sync_user_groups(db, current_user)
        db.refresh(current_user)

    groups = current_user.chat_groups
    
    if not groups:
        if user_role == "PROVINCIAL":
            from app.models.user import District, Region, Camp
            base_query = db.query(ChatGroup).outerjoin(District, ChatGroup.district_id == District.id).outerjoin(Region, ChatGroup.region_id == Region.id).outerjoin(Camp, ChatGroup.camp_id == Camp.id).filter(
                (ChatGroup.province_id == current_user.province_id) |
                (District.province_id == current_user.province_id) |
                (Region.province_id == current_user.province_id) |
                (Camp.province_id == current_user.province_id)
            )
            if group_type:
                base_query = base_query.filter(ChatGroup.group_type == group_type)
            groups = base_query.all()
        elif user_role == "DISTRICT":
            from app.models.user import Region, Camp
            base_query = db.query(ChatGroup).outerjoin(Region, ChatGroup.region_id == Region.id).outerjoin(Camp, ChatGroup.camp_id == Camp.id).filter(
                ((ChatGroup.group_type == "PROVINCIAL") & (ChatGroup.province_id == current_user.province_id)) |
                ((ChatGroup.group_type == "DISTRICT") & (ChatGroup.district_id == current_user.district_id)) |
                ((ChatGroup.group_type == "REGION") & (
                    (ChatGroup.district_id == current_user.district_id) | 
                    (Region.district_id == current_user.district_id)
                )) |
                ((ChatGroup.group_type == "CAMP") & (
                    (ChatGroup.district_id == current_user.district_id) | 
                    (Camp.district_id == current_user.district_id)
                ))
            )
            if group_type:
                base_query = base_query.filter(ChatGroup.group_type == group_type)
            groups = base_query.all()
        elif user_role == "REGION":
            # Region user sees their own Region group 
            # and all Camp groups that belong to their region (using join for safety)
            from app.models.user import Camp
            base_query = db.query(ChatGroup).outerjoin(Camp, ChatGroup.camp_id == Camp.id).filter(
                ((ChatGroup.group_type == "REGION") & (ChatGroup.region_id == current_user.region_id)) |
                ((ChatGroup.group_type == "CAMP") & (
                    (ChatGroup.region_id == current_user.region_id) | 
                    (Camp.region_id == current_user.region_id)
                ))
            )
            if group_type:
                base_query = base_query.filter(ChatGroup.group_type == group_type)
            groups = base_query.all()
        elif user_role == "CAMP":
            # Camp user only sees their parent Region group
            base_query = db.query(ChatGroup).filter(
                (ChatGroup.group_type == "REGION") & (ChatGroup.region_id == current_user.region_id)
            )
            if group_type:
                base_query = base_query.filter(ChatGroup.group_type == group_type)
            groups = base_query.all()
        elif user_role == "AGENT":
            # Agents only see their Region group
            groups = db.query(ChatGroup).filter(ChatGroup.group_type == "REGION", ChatGroup.region_id == current_user.region_id).all()

    res = groups
    
    # Filter by group_type if provided
    if group_type:
        res = [g for g in res if g.group_type == group_type]
    
    # Filter by search if provided
    if search:
        res = [g for g in res if search.lower() in g.name.lower()]
        
    total = len(res)
    start = (page - 1) * limit
    end = start + limit
    paginated_res = res[start:end]
    
    items = []
    for g in paginated_res:
        items.append({
            "id": g.id,
            "name": g.name,
            "group_type": g.group_type,
            "manager_id": g.manager_id,
            "province_id": g.province_id,
            "district_id": g.district_id,
            "region_id": g.region_id,
            "camp_id": g.camp_id,
            "members": [{"id": m.id, "full_name": m.full_name, "role": m.role} for m in g.members]
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/fix-db")
def fix_database_errors(db: Session = Depends(get_db)):
    print("[DEBUG CHAT] fix_database_errors called")
    msgs = []
    try:
        db.execute(text("ALTER TABLE chat_groups ADD COLUMN group_type VARCHAR(50);"))
        db.commit()
        msgs.append("Added group_type to chat_groups")
    except Exception as e:
        db.rollback()
        msgs.append(f"group_type error: {e}")
        
    try:
        db.execute(text("ALTER TABLE chat_groups ADD COLUMN province_id INTEGER REFERENCES provinces(id);"))
        db.commit()
        msgs.append("Added province_id to chat_groups")
    except Exception as e:
        db.rollback()
        msgs.append(f"province_id error: {e}")

    try:
        db.execute(text("ALTER TABLE chat_groups ADD COLUMN district_id INTEGER REFERENCES districts(id);"))
        db.commit()
        msgs.append("Added district_id to chat_groups")
    except Exception as e:
        db.rollback()
        msgs.append(f"district_id error: {e}")

    try:
        db.execute(text("ALTER TABLE chat_groups ADD COLUMN region_id INTEGER REFERENCES regions(id);"))
        db.commit()
        msgs.append("Added region_id to chat_groups")
    except Exception as e:
        db.rollback()
        msgs.append(f"region_id error: {e}")
        
    try:
        db.execute(text("ALTER TABLE chat_groups ADD COLUMN camp_id INTEGER REFERENCES camps(id);"))
        db.commit()
        msgs.append("Added camp_id to chat_groups")
    except Exception as e:
        db.rollback()
        msgs.append(f"camp_id error: {e}")

    try:
        db.execute(text("ALTER TABLE chat_messages ADD COLUMN media_url VARCHAR(500);"))
        db.execute(text("ALTER TABLE chat_messages ALTER COLUMN text DROP NOT NULL;"))
        db.commit()
        msgs.append("Added media_url to chat_messages and made text optional")
    except Exception as e:
        db.rollback()
        msgs.append(f"chat_messages migration error: {e}")
        
    try:
        # Final cleanup: Remove all legacy CAMP groups
        db.execute(text("DELETE FROM chat_group_members WHERE chat_group_id IN (SELECT id FROM chat_groups WHERE group_type = 'CAMP');"))
        db.execute(text("DELETE FROM chat_messages WHERE group_id IN (SELECT id FROM chat_groups WHERE group_type = 'CAMP');"))
        db.execute(text("DELETE FROM chat_groups WHERE group_type = 'CAMP';"))
        db.commit()
        msgs.append("DELETED all legacy CAMP chat groups per client requirement.")
    except Exception as e:
        db.rollback()
        msgs.append(f"Cleanup error: {e}")
        
    print(f"[DEBUG CHAT] fix_db completed with logs: {msgs}")
    return {"status": "Complete", "logs": msgs}

@router.get("/search-users", response_model=List[general_schema.RegionMember])
def search_users_global(
    q: str = Query("", min_length=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Global user search for Super Admin to start direct chats.
    """
    if not current_user.is_superuser and current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Global search restricted to Administrators")

    query = db.query(User).filter(User.is_deleted == False)
    if q:
        query = query.filter(
            (User.full_name.ilike(f"%{q}%")) |
            (User.email.ilike(f"%{q}%")) |
            (User.role.ilike(f"%{q}%"))
        )
    
    users = query.limit(50).all()
    return [{"id": u.id, "name": u.full_name, "role": u.role, "region_id": u.region_id, "district_id": u.district_id, "province_id": u.province_id} for u in users]

@router.post("/groups", response_model=general_schema.ChatGroup)
def create_chat_group(payload: GroupCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    print(f"[DEBUG CHAT] create_chat_group called: {payload.name}, members: {payload.member_ids}")
    # 1. Determine if this is a Direct Chat (1:1) vs a Group Chat
    # Direct chat has only 1 other member in member_ids
    is_direct_chat = len(payload.member_ids or []) == 1
    
    # 2. Apply permissions: Only Admin can create Groups (3+ members). Anyone can create Direct (2 members).
    if not is_direct_chat:
        if not current_user.is_superuser and current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
            print("[DEBUG CHAT] Permission denied for multi-member group creation")
            raise HTTPException(status_code=403, detail="Only Administrators can create multi-member chat groups")

    db_group = ChatGroup(name=payload.name, manager_id=current_user.id)
    
    # Add members
    member_ids = set(payload.member_ids or [])
    member_ids.add(current_user.id) # Always add creator
    members = db.query(User).filter(User.id.in_(list(member_ids))).all()
    print(f"[DEBUG CHAT] Adding {len(members)} members to new group")
    db_group.members = members
    
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    print(f"[DEBUG CHAT] Group created successfully with ID: {db_group.id}")
    return db_group

class DirectChatRequest(BaseModel):
    target_user_id: int

@router.post("/direct", response_model=general_schema.ChatGroup)
def get_or_create_direct_chat(payload: DirectChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    print(f"[DEBUG CHAT] get_or_create_direct_chat called with target: {payload.target_user_id}")
    """
    Open an existing 1:1 chat or create a new one.
    """
    target_user = db.query(User).filter(User.id == payload.target_user_id).first()
    if not target_user:
        print("[DEBUG CHAT] Target user not found")
        raise HTTPException(status_code=404, detail="Target user not found")
        
    # Permission Checks
    cur_role = str(current_user.role).upper()
    is_executive = cur_role == "EXECUTIVE"
    is_provincial = cur_role == "PROVINCIAL"
    is_admin = cur_role in ["SUPER_ADMIN", "ADMINISTRATOR"]
    
    if cur_role in ["CAMP", "AGENT"]:
        print(f"[DEBUG CHAT] Role {cur_role} forbidden from direct chat")
        raise HTTPException(status_code=403, detail="Camp and Agent roles are restricted from 1:1 chats. You participate in the Region group chat.")

    if not is_admin and not is_executive:
        # Provincial check
        if is_provincial:
            if target_user.province_id != current_user.province_id:
                print("[DEBUG CHAT] Provincial scope violation")
                raise HTTPException(status_code=403, detail="Provincial users can only chat with users in their province")

    # 1. Find existing 1:1 chat
    # A 1:1 chat is a group with type "DIRECT" or just 2 members including both.
    existing_group = None
    # We loop through current user's groups to find a 1:1 with the target user
    for group in current_user.chat_groups:
        if len(group.members) == 2:
            member_ids = [m.id for m in group.members]
            if payload.target_user_id in member_ids and current_user.id in member_ids:
                print(f"[DEBUG CHAT] Existing direct chat found: {group.id}")
                existing_group = group
                break
                
    if existing_group:
        return existing_group
        
    # 2. Create new 1:1 chat
    print("[DEBUG CHAT] Creating new direct chat")
    db_group = ChatGroup(
        name=f"{target_user.full_name}",
        manager_id=current_user.id,
        group_type="DIRECT"
    )
    db_group.members = [current_user, target_user]
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    print(f"[DEBUG CHAT] New direct chat created with ID: {db_group.id}")
    return db_group

@router.post("/groups/auto-create")
async def auto_create_hierarchical_groups(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    print(f"[DEBUG CHAT] auto_create_hierarchical_groups initiated by {current_user.id}")
    """
    Initiates hierarchical group synchronization in the background to prevent timeouts.
    """
    if not current_user.is_superuser and current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
        raise HTTPException(status_code=403, detail="Only Administrators can trigger global sync")

    from app.services.chat_service import sync_all_groups
    
    # Run sync in background
    background_tasks.add_task(sync_all_groups, db)

    return {
        "status": "success",
        "message": "Hierarchical synchronization started in the background. It may take a few minutes to complete all groups."
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
    user_role = str(current_user.role).upper()
    group = db.query(ChatGroup).filter(ChatGroup.id == payload.chat_group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Chat group not found")

    if user_role in ["AGENT", "CAMP", "REGION"]:
        if group.group_type != "REGION" or group.region_id != current_user.region_id:
            raise HTTPException(status_code=403, detail=f"{user_role.capitalize()} users can only send messages to their assigned Region group.")

    elif user_role == "REGION":
        if group.group_type != "REGION" or group.region_id != current_user.region_id:
            raise HTTPException(status_code=403, detail="Region users can only send messages to their Region group.")

    msg = ChatMessage(
        group_id=payload.chat_group_id,
        sender_id=current_user.id,
        text=payload.text,
        media_url=payload.media_url
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

    # All members of the region (Region User, Camp Users, Agents)
    query = db.query(User).filter(
        User.region_id == current_user.region_id,
        User.role.in_(ELIGIBLE_REGION_ROLES),
        User.is_deleted == False
    )

    users = query.all()
    return [{"id": u.id, "name": u.full_name, "role": u.role, "region_id": u.region_id, "profession": getattr(u, "profession", None)} for u in users]
ELIGIBLE_DISTRICT_ROLES = ["REGION", "Region", "region", "CAMP", "Camp", "camp", "Agent", "AGENT", "agent"]
ELIGIBLE_PROVINCIAL_ROLES = ["DISTRICT", "District", "district", "District User", "DISTRICT USER"]
ELIGIBLE_NATIONAL_ROLES = ["PROVINCIAL", "Provincial", "provincial", "PROVINCIAL USER", "Provincial User"]

@router.get("/district-members", response_model=List[general_schema.RegionMember])
def get_district_members(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns all regional and camp users belonging to the same district as the logged-in user.
    """
    if not current_user.district_id:
        return []

    query = db.query(User).filter(
        User.district_id == current_user.district_id,
        User.role.in_(ELIGIBLE_DISTRICT_ROLES),
        User.is_deleted == False
    )

    if str(current_user.role).upper() == "CAMP" and current_user.camp_id:
        query = query.filter(User.camp_id == current_user.camp_id)

    users = query.all()
    
    return [{"id": u.id, "name": u.full_name, "role": u.role, "region_id": u.region_id, "district_id": u.district_id, "profession": getattr(u, "profession", None)} for u in users]

@router.get("/provincial-members", response_model=List[general_schema.RegionMember])
def get_provincial_members(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns all district users (accessible by Provincial users).
    """
    users = db.query(User).filter(
        User.role.in_(ELIGIBLE_PROVINCIAL_ROLES),
        User.is_deleted == False
    ).all()
    
    return [{"id": u.id, "name": u.full_name, "role": u.role, "region_id": u.region_id, "district_id": u.district_id, "province_id": u.province_id, "profession": getattr(u, "profession", None)} for u in users]

@router.get("/national-members", response_model=List[general_schema.RegionMember])
def get_national_members(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns all provincial users (accessible by National users).
    """
    users = db.query(User).filter(
        User.role.in_(ELIGIBLE_NATIONAL_ROLES),
        User.is_deleted == False
    ).all()
    
    return [{"id": u.id, "name": u.full_name, "role": u.role, "province_id": u.province_id, "profession": getattr(u, "profession", None)} for u in users]

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
    # Per requirement: Regional users only see Agents and Camp users
    allowed_roles = ELIGIBLE_REGION_ROLES
    cur_role_upper = str(current_user.role).upper()
    
    if cur_role_upper == "REGION":
        allowed_roles = [r for r in ELIGIBLE_REGION_ROLES if "REGION" not in r.upper()]
    elif cur_role_upper == "CAMP":
        allowed_roles = [r for r in ELIGIBLE_REGION_ROLES if "AGENT" in r.upper()]

    query = db.query(User).filter(
        User.region_id == current_user.region_id,
        User.role.in_(allowed_roles),
        User.is_deleted == False
    )

    if str(current_user.role).upper() == "CAMP" and current_user.camp_id:
        query = query.filter(User.camp_id == current_user.camp_id)

    members = query.all()
    
    group.members = members
    db.commit()
    db.refresh(group)
    
    return {
        "group_id": group.id,
        "group_name": group.name,
        "members": [{"id": m.id, "name": m.full_name, "role": m.role, "region_id": m.region_id, "profession": getattr(m, "profession", None)} for m in group.members]
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

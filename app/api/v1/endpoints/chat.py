from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, ChatGroup, ChatMessage
from app.schemas import general as general_schema
from pydantic import BaseModel

router = APIRouter()

class MessageCreate(BaseModel):
    chat_group_id: int
    text: str

class GroupCreate(BaseModel):
    name: str
    member_ids: List[int]

@router.get("/groups", response_model=List[general_schema.ChatGroup])
def get_chat_groups(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Super admins see everything, others see groups they are members of
    if current_user.is_superuser:
        return db.query(ChatGroup).all()
    return current_user.chat_groups

@router.post("/groups", response_model=general_schema.ChatGroup)
def create_chat_group(payload: GroupCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    Automatically create or update chat groups for every manager and their subordinates.
    """
    # 1. Get all managers (users who are parents to other users)
    managers = db.query(User).filter(User.subordinates.any()).all()
    
    created_count = 0
    updated_count = 0
    
    for manager in managers:
        group_name = f"{manager.full_name}'s Team"
        existing_group = db.query(ChatGroup).filter(
            ChatGroup.manager_id == manager.id,
            ChatGroup.name == group_name
        ).first()
        
        # Desired members based on current hierarchy
        current_members = [manager] + manager.subordinates
        
        if not existing_group:
            # Create new group
            new_group = ChatGroup(name=group_name, manager_id=manager.id)
            new_group.members = current_members
            db.add(new_group)
            created_count += 1
        else:
            # Update existing group members to reflect the current subordinates
            existing_group.members = current_members
            updated_count += 1
            
    db.commit()
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
    
    if group.manager_id != current_user.id and not current_user.is_superuser:
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

from datetime import timedelta, datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app import models
from app.schemas import user as user_schema
from app.core import security
from app.core.config import settings
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User

router = APIRouter()

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    full_name: str
    role: str
    avatar_url: str | None = None
    permissions: str | None = None
    province_id: int | None = None
    district_id: int | None = None
    region_id: int | None = None
    camp_id: int | None = None

@router.post("/login/access-token", response_model=LoginResponse)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    print(f"Login attempt for: {form_data.username}")
    user = db.query(User).filter(User.email == form_data.username).first()
    print(f"User found: {user is not None}")
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        print("Invalid password or user not found")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    
    # Update last_seen timestamp
    user.last_seen = datetime.utcnow()
    db.add(user)
    # Sync groups on login to ensure memberships are up-to-date
    # Wrapped in try-except to prevent login failure if chat sync has issues
    try:
        from app.services.chat_service import sync_user_groups
        sync_user_groups(db, user)
    except Exception as e:
        db.rollback() # VERY IMPORTANT: Reset the transaction state
        print(f"Error syncing user groups for {user.email}: {e}")
        # We don't raise here, so login continues
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Debug log to check avatar_url
    print(f"DEBUG: User avatar_url: {user.avatar_url}")
    
    # Inherit permissions from role if individual permissions are missing
    effective_permissions = user.permissions
    if not effective_permissions and user.system_role:
        effective_permissions = user.system_role.permissions
        
    # Determine the display role
    display_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
    if user.system_role:
        display_role = user.system_role.name
        
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user_id": user.id,
        "full_name": user.full_name,
        "role": display_role,
        "avatar_url": str(user.avatar_url) if user.avatar_url else None,
        "permissions": effective_permissions,
        "province_id": user.province_id,
        "district_id": user.district_id,
        "region_id": user.region_id,
        "camp_id": user.camp_id,
    }

@router.post("/login/test-token", response_model=user_schema.User)
def test_token(current_user: User = Depends(get_current_user)) -> Any:
    """
    Test access token
    """
    return current_user

@router.get("/users/me", response_model=user_schema.User)
def read_user_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user.
    """
    # 1. Populate Hierarchy Names
    if current_user.camp_id and current_user.camp:
        current_user.camp_name = current_user.camp.name
    if current_user.region_id and current_user.region:
        current_user.region_name = current_user.region.name
    if current_user.district_id and current_user.district:
        current_user.district_name = current_user.district.name
    if current_user.province_id and current_user.province:
        current_user.province_name = current_user.province.name
        
    # 2. Populate Supervisor Name (mostly for Agents)
    if current_user.parent_id:
        supervisor = db.query(User).filter(User.id == current_user.parent_id).first()
        if supervisor:
            current_user.supervisor_name = supervisor.full_name

    # 3. Populate Operational Statistics based on role
    role = str(current_user.role).upper()
    
    if role == "CAMP":
        # Agents in this camp
        current_user.managed_agents_count = db.query(User).filter(
            User.camp_id == current_user.camp_id, 
            User.role == "AGENT"
        ).count()
        
    elif role == "REGION":
        # Camps in this region
        current_user.managed_camps_count = db.query(models.user.Camp).filter(
            models.user.Camp.region_id == current_user.region_id
        ).count()
        # Agents in this region
        current_user.managed_agents_count = db.query(User).filter(
            User.region_id == current_user.region_id,
            User.role == "AGENT"
        ).count()
        
    elif role == "DISTRICT":
        # Regions in this district
        current_user.managed_regions_count = db.query(models.user.Region).filter(
            models.user.Region.district_id == current_user.district_id
        ).count()
        # Camps in this district
        current_user.managed_camps_count = db.query(models.user.Camp).filter(
            models.user.Camp.district_id == current_user.district_id
        ).count()
        
    elif role == "PROVINCIAL":
        # Districts in this province
        current_user.managed_districts_count = db.query(models.user.District).filter(
            models.user.District.province_id == current_user.province_id
        ).count()
        # Regions in this province
        current_user.managed_regions_count = db.query(models.user.Region).filter(
            models.user.Region.province_id == current_user.province_id
        ).count()

    return current_user

@router.put("/users/me", response_model=user_schema.User)
def update_user_me(
    *,
    db: Session = Depends(get_db),
    user_in: user_schema.UserUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update my own profile.
    """
    update_data = user_in.model_dump(exclude_unset=True)
    
    # Don't allow self-changing role via this endpoint
    if "role" in update_data:
        del update_data["role"]
    if "role_id" in update_data:
        del update_data["role_id"]
        
    # Update password if provided
    if "password" in update_data:
        from app.core.security import get_password_hash
        current_user.hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        
    # Update other fields
    for field, value in update_data.items():
        setattr(current_user, field, value)
        
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/users/me/avatar")
async def update_avatar(
    *,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update current user's avatar.
    """
    from app.utils.cloudinary import upload_image
    
    url = upload_image(file.file, folder="ccns_avatars")
    if not url:
        raise HTTPException(status_code=500, detail="Failed to upload image")
    
    current_user.avatar_url = url
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

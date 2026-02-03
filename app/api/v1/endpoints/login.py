from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.token import Token

router = APIRouter()

@router.post("/login/access-token", response_model=Token)
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
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
        "user_id": user.id,
        "full_name": user.full_name,
        "role": user.role
    }

@router.post("/login/test-token", response_model=Any)
def test_token(current_user: User = Depends(get_current_user)) -> Any:
    """
    Test access token
    """
    return current_user

@router.get("/users/me", response_model=Any)
def read_user_me(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get current user.
    """
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

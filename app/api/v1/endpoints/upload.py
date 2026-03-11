from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import Any
import cloudinary
import cloudinary.uploader
from app.core.config import settings
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()

# Configure Cloudinary
if settings.CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET
    )

@router.post("/", response_model=Any)
def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Upload a file to Cloudinary.
    """
    print("DEBUG: Upload request received")
    
    if not settings.CLOUDINARY_CLOUD_NAME:
         print("DEBUG: Cloudinary config missing")
         raise HTTPException(status_code=500, detail="Cloudinary configuration missing on server.")

    print(f"DEBUG: Config found. Cloud: {settings.CLOUDINARY_CLOUD_NAME}")

    try:
        # Upload to Cloudinary
        print("DEBUG: Calling cloudinary.uploader.upload...")
        # Seek to start using sync method on the underlying file
        file.file.seek(0)
        
        response = cloudinary.uploader.upload(file.file, resource_type="auto")
        
        print("DEBUG: Upload successful!")
        return {
            "url": response.get("secure_url"),
            "file_url": response.get("secure_url"), # Alias for mobile
            "public_id": response.get("public_id"),
            "original_filename": file.filename,
            "file_name": file.filename # Alias for mobile
        }
        
    except Exception as e:
        print(f"DEBUG: Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

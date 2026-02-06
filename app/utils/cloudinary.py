import cloudinary
import cloudinary.uploader
from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

def upload_file(file, folder="ccns_reports"):
    """
    Upload a file (image, video, pdf, etc.) to cloudinary and return the URL.
    """
    try:
        result = cloudinary.uploader.upload(file, folder=folder, resource_type="auto")
        return result.get("secure_url")
    except Exception as e:
        print(f"Cloudinary upload failed: {e}")
        return None

# Alias for backward compatibility
upload_image = upload_file

def delete_image(public_id):
    """
    Delete an image from cloudinary using its public_id.
    """
    try:
        cloudinary.uploader.destroy(public_id)
        return True
    except Exception as e:
        print(f"Cloudinary delete failed: {e}")
        return False

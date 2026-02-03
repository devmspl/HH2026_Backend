from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, RoleChecker
from app.db.session import get_db
from app.models.user import User, UserRole, Report, ReportStatus, ReportImage, ReportEditHistory
from app.schemas import general as general_schema
from app.core.audit import log_action
import uuid

router = APIRouter()

@router.get("/", response_model=List[general_schema.Report])
def read_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve reports.
    Level based visibility should be applied here.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        return db.query(Report).offset(skip).limit(limit).all()
    elif current_user.role == UserRole.AGENT:
        return db.query(Report).filter(Report.agent_id == current_user.id).all()
    else:
        # Placeholder for hierarchy tracking: reports from subordinates
        # For demo, returning all
        return db.query(Report).offset(skip).limit(limit).all()

@router.post("/", response_model=general_schema.Report)
def create_report(
    *,
    db: Session = Depends(get_db),
    report_in: general_schema.ReportCreate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create new report.
    """
    db_obj = Report(
        agent_id=report_in.agent_id,
        title=report_in.title,
        description=report_in.description,
        gps_lat=report_in.gps_lat,
        gps_lng=report_in.gps_lng,
        confirmation_no=f"CONF-{uuid.uuid4().hex[:8].upper()}",
        status=report_in.status or ReportStatus.PENDING
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    # Process images if provided
    if report_in.images:
        from app.utils.cloudinary import upload_image
        for img_data in report_in.images:
            image_url = img_data
            # If it looks like base64, upload to cloudinary
            if img_data.startswith("data:"):
                uploaded_url = upload_image(img_data)
                if uploaded_url:
                    image_url = uploaded_url
            
            db_image = ReportImage(report_id=db_obj.id, image_url=image_url)
            db.add(db_image)
        db.commit()
        db.refresh(db_obj)

    return db_obj

@router.put("/{report_id}", response_model=general_schema.Report)
def update_report(
    *,
    db: Session = Depends(get_db),
    report_id: int,
    report_in: general_schema.ReportUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update a report and track history.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    update_data = report_in.dict(exclude_unset=True)
    
    # Store history
    changes = ", ".join([f"{k} changed to {v}" for k, v in update_data.items()])
    history = ReportEditHistory(
        report_id=report_id,
        user_id=current_user.id,
        changes=changes
    )
    db.add(history)
    
    for field in update_data:
        if field == "images" and update_data["images"] is not None:
            # Clear old images and add new ones
            db.query(ReportImage).filter(ReportImage.report_id == report_id).delete()
            from app.utils.cloudinary import upload_image
            for img_data in update_data["images"]:
                image_url = img_data
                if img_data.startswith("data:"):
                    uploaded_url = upload_image(img_data)
                    if uploaded_url:
                        image_url = uploaded_url
                db_image = ReportImage(report_id=report_id, image_url=image_url)
                db.add(db_image)
        else:
            setattr(report, field, update_data[field])
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    log_action(db, current_user.id, "UPDATE_REPORT", f"Updated report {report.confirmation_no}. Changes: {changes}")
    
    return report

@router.post("/{report_id}/images")
async def upload_report_image(
    *,
    db: Session = Depends(get_db),
    report_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload an image for a report using Cloudinary.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    from app.utils.cloudinary import upload_image
    
    image_url = upload_image(file.file)
    if not image_url:
        raise HTTPException(status_code=500, detail="Failed to upload image to Cloudinary")
    
    db_image = ReportImage(report_id=report_id, image_url=image_url)
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    return {"id": db_image.id, "image_url": db_image.image_url}

@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a report.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Check permissions? Assuming Admin can delete.
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMINISTRATOR]:
         raise HTTPException(status_code=403, detail="Not authorized to delete reports")

    conf_no = report.confirmation_no
    db.delete(report)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_REPORT", f"Deleted report {conf_no}")
    
    return {"message": "Report deleted successfully"}

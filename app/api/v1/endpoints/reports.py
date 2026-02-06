from typing import Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, RoleChecker
from app.db.session import get_db
from app.models.user import User, UserRole, Report, ReportMedia, ReportEditHistory
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
    status: Optional[str] = None,
    agent_id: Optional[int] = None,
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Any:
    """
    Retrieve reports with search and filter capabilities.
    """
    query = db.query(Report)

    # Search (title, description, confirmation_no)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Report.title.ilike(search_filter)) |
            (Report.description.ilike(search_filter)) |
            (Report.confirmation_no.ilike(search_filter))
        )

    # Filters
    if status and status != "all":
        query = query.filter(Report.status == status)
    
    if agent_id:
        query = query.filter(Report.agent_id == agent_id)

    if start_date:
        query = query.filter(Report.created_at >= start_date)
    if end_date:
        query = query.filter(Report.created_at <= end_date)

    # Visibility constraints
    if current_user.role == UserRole.AGENT:
        query = query.filter(Report.agent_id == current_user.id)
    # For demo, keeping it simple; admins see all matching filters.

    reports = query.order_by(Report.created_at.desc()).offset(skip).limit(limit).all()

    # Populate names (manual population because relationship is one-way or to keep it simple)
    # Alternatively, use sqlalchemy joinedload if models had proper relationships defined for names.
    # The models have agent relationship already.
    
    for report in reports:
        if report.agent:
            report.agent_name = report.agent.full_name
            report.agent_role = report.agent.role
            report.agent_email = report.agent.email
            report.agent_phone = report.agent.phone
        
        for edit in report.edits:
            edit_user = db.query(User).filter(User.id == edit.user_id).first()
            if edit_user:
                edit.user_name = edit_user.full_name

    return reports

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
        status=report_in.status or "pending"
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    # Process media if provided
    if report_in.media:
        from app.utils.cloudinary import upload_image # Keep name for now or update later
        for media_item in report_in.media:
            file_url = media_item.get("url")
            file_type = media_item.get("type", "image")
            file_name = media_item.get("name")
            
            # If it looks like base64, upload to cloudinary
            if file_url and file_url.startswith("data:"):
                # Pass resource_type auto to handle videos/docs
                uploaded_url = upload_image(file_url) # Cloudinary uploader.upload handles this
                if uploaded_url:
                    file_url = uploaded_url
            
            db_media = ReportMedia(
                report_id=db_obj.id, 
                file_url=file_url,
                file_type=file_type,
                file_name=file_name
            )
            db.add(db_media)
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
    
    # Track changes for audit trail
    changes_list = []
    for field, new_value in update_data.items():
        if field == "media":
            continue # Handle media separately
        
        old_value = getattr(report, field)
        if old_value != new_value:
            changes_list.append(f"{field}: {old_value} -> {new_value}")
    
    if changes_list:
        changes_str = "; ".join(changes_list)
        history = ReportEditHistory(
            report_id=report_id,
            user_id=current_user.id,
            changes=changes_str
        )
        db.add(history)
    
    for field in update_data:
        if field == "media" and update_data["media"] is not None:
            # Clear old media and add new one
            from app.models.user import ReportMedia
            db.query(ReportMedia).filter(ReportMedia.report_id == report_id).delete()
            from app.utils.cloudinary import upload_image
            for media_item in update_data["media"]:
                file_url = media_item.get("url")
                file_type = media_item.get("type", "image")
                file_name = media_item.get("name")
                
                if file_url and file_url.startswith("data:"):
                    uploaded_url = upload_image(file_url)
                    if uploaded_url:
                        file_url = uploaded_url
                
                db_media = ReportMedia(
                    report_id=report_id, 
                    file_url=file_url,
                    file_type=file_type,
                    file_name=file_name
                )
                db.add(db_media)
        else:
            setattr(report, field, update_data[field])
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    log_action(db, current_user.id, "UPDATE_REPORT", f"Updated report {report.confirmation_no}. Changes: {changes_str if 'changes_str' in locals() else 'No data changes'}")
    
    return report

@router.post("/{report_id}/media")
async def upload_report_media(
    *,
    db: Session = Depends(get_db),
    report_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Upload media for a report using Cloudinary.
    """
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    from app.utils.cloudinary import upload_file
    
    file_url = upload_file(file.file)
    if not file_url:
        raise HTTPException(status_code=500, detail="Failed to upload file to Cloudinary")
    
    # Detect file type simple
    file_type = "image"
    if file.content_type:
        if "video" in file.content_type: file_type = "video"
        elif "pdf" in file.content_type: file_type = "pdf"
    
    db_media = ReportMedia(
        report_id=report_id, 
        file_url=file_url,
        file_type=file_type,
        file_name=file.filename
    )
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    
    return {"id": db_media.id, "file_url": db_media.file_url, "file_type": db_media.file_type}

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

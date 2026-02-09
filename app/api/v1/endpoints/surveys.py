from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User, Survey, SurveyStatus, SurveyType
from app.schemas.user import SurveyOut, SurveyCreate, SurveyUpdate
import csv
import io

from app.core.audit import log_action

router = APIRouter()

@router.get("/", response_model=List[SurveyOut])
def get_surveys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all surveys (Administrators) or assigned surveys (Agents).
    """
    query = db.query(Survey)

    from app.models.user import UserRole, TargetRespondents
    
    if current_user.role == UserRole.AGENT:
        # Agents only see ACTIVE surveys assigned to them
        query = query.filter(Survey.status == SurveyStatus.ACTIVE)
        query = query.filter(
            (Survey.target_respondents == TargetRespondents.ALL) |
            (Survey.target_users.any(User.id == current_user.id))
        )
    
    surveys = query.order_by(Survey.created_at.desc()).all()
    
    # Map target_user_ids for each survey
    results = []
    for s in surveys:
        out = SurveyOut.from_orm(s)
        out.target_user_ids = [u.id for u in s.target_users]
        results.append(out)
    return results

@router.get("/{survey_id}", response_model=SurveyOut)
def get_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get survey by ID.
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    out = SurveyOut.from_orm(survey)
    out.target_user_ids = [u.id for u in survey.target_users]
    return out

@router.post("/", response_model=SurveyOut)
def create_survey(
    survey_in: SurveyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new survey in DRAFT status.
    """
    survey_data = survey_in.dict(exclude={"target_user_ids"})
    survey = Survey(
        **survey_data,
        created_by=current_user.id
    )
    
    if survey_in.target_user_ids:
        target_users = db.query(User).filter(User.id.in_(survey_in.target_user_ids)).all()
        survey.target_users = target_users
        
    db.add(survey)
    db.commit()
    db.refresh(survey)
    
    # Map target_user_ids for response
    survey_out = SurveyOut.from_orm(survey)
    survey_out.target_user_ids = [u.id for u in survey.target_users]
    
    log_action(db, current_user.id, "CREATE_SURVEY", f"Created {survey.form_type.value} '{survey.name}'")
    
    return survey_out

@router.put("/{survey_id}/launch", response_model=SurveyOut)
def launch_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Launch a survey (set status to ACTIVE).
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.status == SurveyStatus.ENDED:
        raise HTTPException(status_code=400, detail="Cannot launch an ended survey")
    
    survey.status = SurveyStatus.ACTIVE
    db.commit()
    db.refresh(survey)
    
    log_action(db, current_user.id, "LAUNCH_SURVEY", f"Launched survey '{survey.name}' (ID: {survey_id})")
    
    return survey

@router.put("/{survey_id}/end", response_model=SurveyOut)
def end_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    End a survey (set status to ENDED).
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    survey.status = SurveyStatus.ENDED
    db.commit()
    db.refresh(survey)
    
    log_action(db, current_user.id, "END_SURVEY", f"Ended survey '{survey.name}' (ID: {survey_id})")
    
    return survey

@router.put("/{survey_id}/status", response_model=SurveyOut)
def update_survey_status(
    survey_id: int,
    status: SurveyStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update survey status (generic endpoint).
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    old_status = survey.status
    survey.status = status
    db.commit()
    db.refresh(survey)
    
    log_action(db, current_user.id, "UPDATE_SURVEY_STATUS", f"Updated status of survey '{survey.name}' from {old_status} to {status}")
    
    return survey

@router.put("/{survey_id}", response_model=SurveyOut)
def update_survey(
    survey_id: int,
    survey_in: SurveyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a survey.
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    update_data = survey_in.dict(exclude_unset=True, exclude={"target_user_ids"})
    for field, value in update_data.items():
        setattr(survey, field, value)
    
    if survey_in.target_user_ids is not None:
        target_users = db.query(User).filter(User.id.in_(survey_in.target_user_ids)).all()
        survey.target_users = target_users
        
    db.commit()
    db.refresh(survey)
    
    # Map target_user_ids for response
    survey_out = SurveyOut.from_orm(survey)
    survey_out.target_user_ids = [u.id for u in survey.target_users]
    
    log_action(db, current_user.id, "UPDATE_SURVEY", f"Updated survey '{survey.name}' (ID: {survey_id})")
    
    return survey_out

@router.delete("/{survey_id}")
def delete_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a survey.
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    survey_name = survey.name
    db.delete(survey)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_SURVEY", f"Deleted survey '{survey_name}' (ID: {survey_id})")
    
    return {"message": "Survey deleted successfully"}

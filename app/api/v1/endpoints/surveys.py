from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.core.auth import get_current_user, RoleChecker
from app.db.session import get_db
from app.models.user import User, Survey, SurveyStatus, SurveyType, UserRole, NotificationLog
from app.schemas.user import SurveyOut, SurveyCreate, SurveyUpdate
import csv
import io

from app.core.audit import log_action

router = APIRouter()

def _notify_assigned_agents(db: Session, survey: Survey, agent_ids: List[int], title: str, message: str, icon: str = "Assignment"):
    """Send an in-app notification to the list of agent IDs."""
    for uid in agent_ids:
        log = NotificationLog(
            recipient_id=uid,
            type="push",
            title=title,
            message=message,
            icon=icon,
            status="sent"
        )
        db.add(log)
    db.flush()  # flush within the same transaction

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
        out = SurveyOut.model_validate(s).model_copy(update={"target_user_ids": [u.id for u in s.target_users]})
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
    
    out = SurveyOut.model_validate(survey).model_copy(update={"target_user_ids": [u.id for u in survey.target_users]})
    return out

@router.post("/", response_model=SurveyOut)
def create_survey(
    survey_in: SurveyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN])),
):
    """
    Create a new survey in DRAFT status.

    Business rule:
    - Only System Super Admin can create national/regional surveys.
    """
    try:
        survey_data = survey_in.model_dump(exclude={"target_user_ids"})
        # Normalize Enum-like values to string for DB
        for key in ("form_type", "target_respondents", "attachment_required", "status"):
            if key in survey_data and hasattr(survey_data[key], "value"):
                survey_data[key] = survey_data[key].value

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

        # Notify assigned agents about the new survey
        assigned_ids = [u.id for u in survey.target_users]
        if assigned_ids:
            notify_title = f"New Survey Assigned"
            notify_msg = (
                f"You have been assigned to: '{survey.name}'\n"
                f"Type: {survey.form_type}\n"
                f"Description: {survey.description or 'N/A'}"
            )
            _notify_assigned_agents(db, survey, assigned_ids, notify_title, notify_msg, icon="Assignment")
            db.commit()

        survey_out = SurveyOut.model_validate(survey).model_copy(update={"target_user_ids": assigned_ids})
        log_action(db, current_user.id, "CREATE_SURVEY", f"Created {survey.form_type} '{survey.name}'")
        return survey_out
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Survey create failed: {str(e)}",
        )

@router.put("/{survey_id}/launch", response_model=SurveyOut)
def launch_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN])),
):
    """
    Launch a survey (set status to ACTIVE).

    Business rule:
    - Only System Super Admin can launch surveys.
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    if survey.status == SurveyStatus.ENDED:
        raise HTTPException(status_code=400, detail="Cannot launch an ended survey")
    
    survey.status = SurveyStatus.ACTIVE
    db.commit()
    db.refresh(survey)

    # Notify all assigned agents (or all agents if target is All)
    target_val = str(survey.target_respondents)
    if target_val in ["All Agents", "TargetRespondents.ALL"]:
        from app.models.user import UserRole
        field_roles = [UserRole.AGENT, UserRole.CAMP, UserRole.REGION, UserRole.DISTRICT, UserRole.PROVINCIAL]
        all_field_users = db.query(User).filter(User.role.in_(field_roles), User.is_deleted == False).all()
        notify_targets = [u.id for u in all_field_users]
    else:
        notify_targets = [u.id for u in survey.target_users]

    if notify_targets:
        try:
            # We use a separate nested transaction or just commit again after notifications
            launch_title = "New Survey Active"
            launch_msg = f"🚀 '{survey.name}' is now ACTIVE. Please start submissions."
            _notify_assigned_agents(db, survey, notify_targets, launch_title, launch_msg, icon="RocketLaunch")
            db.commit()
        except Exception as e:
            db.rollback() # Rollback the notifications only
            print(f"Notification error: {str(e)}")
            pass

    # Log action in a fresh transaction state if needed
    log_action(db, current_user.id, "LAUNCH_SURVEY", f"Launched survey '{survey.name}' (ID: {survey_id})")
    return SurveyOut.model_validate(survey).model_copy(update={"target_user_ids": [u.id for u in survey.target_users]})

@router.put("/{survey_id}/end", response_model=SurveyOut)
def end_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN])),
):
    """
    End a survey (set status to ENDED).

    Business rule:
    - Only System Super Admin can end surveys.
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    survey.status = SurveyStatus.ENDED
    db.commit()
    db.refresh(survey)
    
    log_action(db, current_user.id, "END_SURVEY", f"Ended survey '{survey.name}' (ID: {survey_id})")
    return SurveyOut.model_validate(survey).model_copy(update={"target_user_ids": [u.id for u in survey.target_users]})

@router.put("/{survey_id}/status", response_model=SurveyOut)
def update_survey_status(
    survey_id: int,
    status: SurveyStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN])),
):
    """
    Update survey status (generic endpoint).

    Business rule:
    - Only System Super Admin can change survey lifecycle state.
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    old_status = survey.status
    survey.status = status
    db.commit()
    db.refresh(survey)
    
    log_action(db, current_user.id, "UPDATE_SURVEY_STATUS", f"Updated status of survey '{survey.name}' from {old_status} to {status}")
    return SurveyOut.model_validate(survey).model_copy(update={"target_user_ids": [u.id for u in survey.target_users]})

@router.put("/{survey_id}", response_model=SurveyOut)
def update_survey(
    survey_id: int,
    survey_in: SurveyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN])),
):
    """
    Update a survey.

    Business rule:
    - Only System Super Admin can edit surveys.
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    update_data = survey_in.model_dump(exclude_unset=True, exclude={"target_user_ids"})
    for field, value in update_data.items():
        setattr(survey, field, value)
    
    if survey_in.target_user_ids is not None:
        target_users = db.query(User).filter(User.id.in_(survey_in.target_user_ids)).all()
        survey.target_users = target_users
        
    db.commit()
    db.refresh(survey)

    # Notify newly assigned agents about survey update
    updated_agent_ids = [u.id for u in survey.target_users]
    if updated_agent_ids:
        update_msg = (
            f"📝 Survey Updated: '{survey.name}' has been updated and you are assigned to it.\n"
            f"Type: {survey.form_type}\n"
            f"Please review the updated survey details and complete your submission."
        )
        _notify_assigned_agents(db, survey, updated_agent_ids, update_msg)
        db.commit()

    survey_out = SurveyOut.model_validate(survey).model_copy(update={"target_user_ids": updated_agent_ids})
    log_action(db, current_user.id, "UPDATE_SURVEY", f"Updated survey '{survey.name}' (ID: {survey_id})")
    return survey_out

@router.delete("/{survey_id}")
def delete_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker([UserRole.SUPER_ADMIN])),
):
    """
    Delete a survey.

    Business rule:
    - Only System Super Admin can delete surveys.
    """
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    survey_name = survey.name
    db.delete(survey)
    db.commit()
    
    log_action(db, current_user.id, "DELETE_SURVEY", f"Deleted survey '{survey_name}' (ID: {survey_id})")
    
    return {"message": "Survey deleted successfully"}

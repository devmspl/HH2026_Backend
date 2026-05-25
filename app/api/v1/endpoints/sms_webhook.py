import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.models.user import (
    User, Survey, Report, ReportStatus, NationalCrop, RegionalCrop, 
    SurveyStatus, SurveyType
)

router = APIRouter()
logger = logging.getLogger(__name__)

class SMSWebhookPayload(BaseModel):
    sender: str
    message: str
    timestamp: Optional[str] = None
    gateway_id: Optional[str] = None

@router.post("/receive", status_code=status.HTTP_200_OK)
def receive_sms_webhook(payload: SMSWebhookPayload, db: Session = Depends(get_db)):
    """
    Webhook to receive parsed SMS survey data from Skewset SMS Gateway.
    Format expected in payload.message:
    NS|Ag:John|Reg:North|TF:250|PF:200|SR:5|Ma:10|Wh:8
    """
    logger.info(f"Received SMS Webhook from {payload.sender}: {payload.message}")

    if not payload.message:
        raise HTTPException(status_code=400, detail="Empty SMS message")

    parts = payload.message.split("|")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid SMS format")

    form_type_code = parts[0]
    if form_type_code == "NS":
        target_survey_type = SurveyType.NATIONAL.value
    elif form_type_code == "RS":
        target_survey_type = SurveyType.REGIONAL.value
    else:
        raise HTTPException(status_code=400, detail=f"Unknown survey type code: {form_type_code}")

    # 1. Resolve Agent
    # Remove '+' or spaces from numbers just in case, though direct match is best
    clean_sender = payload.sender.strip().replace(" ", "")
    agent = db.query(User).filter(
        User.phone.like(f"%{clean_sender[-9:]}%"), # Match last 9 digits to handle +country code variations
        User.is_active == True,
        User.is_deleted == False
    ).first()

    if not agent:
        logger.error(f"Agent not found for phone number: {payload.sender}")
        raise HTTPException(status_code=404, detail="Agent not found based on sender number")

    # 2. Get Active Survey
    survey = db.query(Survey).filter(
        Survey.form_type == target_survey_type,
        Survey.status == SurveyStatus.ACTIVE.value
    ).first()

    if not survey:
        logger.error(f"No active survey found for type: {target_survey_type}")
        raise HTTPException(status_code=404, detail="No active survey available for this type")

    # 3. Parse SMS Metrics and Crops
    total_farmers = 0
    participating_farmers = 0
    spoiled_responses = 0
    parsed_crops = []

    for part in parts[1:]:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip()
        value = value.strip()
        
        try:
            if key == "Ag" or key == "Reg":
                continue # Handled by DB lookup
            elif key == "TF":
                total_farmers = int(value)
            elif key == "PF":
                participating_farmers = int(value)
            elif key == "SR":
                spoiled_responses = int(value)
            else:
                # It's a crop yield, key is first 2 letters of crop name (e.g. "Ma" for Maize)
                yield_tonnes = float(value)
                
                # Look up actual crop in DB
                crop_name = key
                crop_id = None
                family_name = "Unknown"
                
                if form_type_code == "NS":
                    crop = db.query(NationalCrop).filter(NationalCrop.crop_name.ilike(f"{key}%")).first()
                    if crop:
                        crop_name = crop.crop_name
                        crop_id = crop.id
                        family_name = crop.family.family_name if crop.family else "Unknown"
                else:
                    crop = db.query(RegionalCrop).filter(RegionalCrop.crop_name.ilike(f"{key}%")).first()
                    if crop:
                        crop_name = crop.crop_name
                        crop_id = crop.id
                        family_name = crop.family.family_name if crop.family else "Unknown"

                parsed_crops.append({
                    "crop_id": crop_id,
                    "crop_name": crop_name,
                    "family_name": family_name,
                    "yield_tonnes": yield_tonnes
                })
        except ValueError:
            logger.warning(f"Could not parse numeric value in SMS part: {part}")
            continue

    # 4. Construct Survey Data JSON
    survey_data = {
        "total_farmers": total_farmers,
        "participating_farmers": participating_farmers,
        "spoiled_responses": spoiled_responses,
        "crops": parsed_crops,
        "source": "sms_gateway"
    }

    # 5. Save or Update Report (Duplicate Prevention)
    existing_report = db.query(Report).filter(
        Report.agent_id == agent.id,
        Report.survey_id == survey.id
    ).first()

    if existing_report:
        existing_report.title = f"SMS Submission: {survey.name}"
        existing_report.description = f"Updated via SMS Webhook on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        existing_report.survey_data = json.dumps(survey_data)
        existing_report.status = ReportStatus.PENDING
        action_msg = "Updated existing report via SMS"
    else:
        new_report = Report(
            agent_id=agent.id,
            survey_id=survey.id,
            title=f"SMS Submission: {survey.name}",
            description=f"Submitted via SMS Webhook on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            status=ReportStatus.PENDING,
            gps_lat=agent.last_lat or 0.0,
            gps_lng=agent.last_lng or 0.0,
            province_id=agent.province_id,
            district_id=agent.district_id,
            region_id=agent.region_id,
            camp_id=agent.camp_id,
            survey_data=json.dumps(survey_data)
        )
        db.add(new_report)
        action_msg = "Created new report via SMS"

    db.commit()
    logger.info(action_msg)

    return {"status": "success", "message": action_msg, "parsed_crops_count": len(parsed_crops)}

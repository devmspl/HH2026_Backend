import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.models.user import (
    User, Survey, Report, ReportStatus, NationalCrop, RegionalCrop,
    SurveyStatus, SurveyType, NotificationLog
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Config from client
EXPECTED_TOKEN = "Bearer HbCrmTefVoQ5r2YFzB3grWkywt4kDhzLtxRnuIc1Ph8zFyM78gCNKcsPyWu8nZSX"
EXPECTED_USERNAME = "skewset"
EXPECTED_ORG = "skewHH2026"


def _parse_gateway_timestamp(ts: Optional[str]) -> datetime:
    """
    Parse ISO timestamp from gateway. Falls back to current server time if missing/malformed.
    """
    if not ts:
        return datetime.now()
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        logger.warning(f"[SMS-WEBHOOK] Could not parse timestamp '{ts}', using server time")
        return datetime.now()


def _log_inbound_sms(db: Session, sender: str, message: str, received_at: str,
                     status_str: str, agent_id: int = 1):
    """
    Write every inbound SMS attempt to NotificationLog for full auditing.
    Caller is responsible for committing the session.
    """
    try:
        log_message = (
            f"INBOUND SMS | sender:{sender} | "
            f"received_at:{received_at} | "
            f"status:{status_str} | "
            f"message:{message[:120]}"
        )
        db.add(NotificationLog(
            recipient_id=agent_id,
            type="sms_inbound",
            title="Inbound SMS Gateway",
            message=log_message,
            status=status_str,
            icon="Sms",
        ))
    except Exception as e:
        logger.error(f"[SMS-WEBHOOK] Failed to write inbound log: {e}")


@router.post("/receive", status_code=status.HTTP_200_OK)
async def receive_sms_webhook(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    username: Optional[str] = Header(None),
    org_slug: Optional[str] = Header(None),
    phone_number: Optional[str] = Header(None),
    timestamp: Optional[str] = Header(None)
):
    """
    Webhook endpoint to receive incoming SMS survey data from Skewset SMS Gateway.
    Format expects auth and metadata in headers, and raw text in the body.
    """
    # ── 1. Authentication & Header Validation ─────────────────────────────────
    if authorization != EXPECTED_TOKEN:
        logger.warning(f"[SMS-WEBHOOK] Unauthorized access attempt. Token: {authorization}")
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if username != EXPECTED_USERNAME or org_slug != EXPECTED_ORG:
        logger.warning(f"[SMS-WEBHOOK] Invalid username/org. User: {username}, Org: {org_slug}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not phone_number:
        logger.warning("[SMS-WEBHOOK] Missing phone_number header")
        raise HTTPException(status_code=400, detail="Missing phone_number header")

    # ── 2. Parse Body and Metadata ────────────────────────────────────────────
    body_bytes = await request.body()
    message = body_bytes.decode("utf-8").strip()
    
    submission_time = _parse_gateway_timestamp(timestamp)
    received_at = submission_time.strftime("%Y-%m-%d %H:%M:%S")

    logger.info(
        f"[SMS-WEBHOOK] Incoming | sender={phone_number} | "
        f"received_at={received_at} | message={message}"
    )

    if not message:
        logger.warning(f"[SMS-WEBHOOK] Empty message from {phone_number}")
        raise HTTPException(status_code=400, detail="Empty SMS message")

    parts = [p.strip() for p in message.split("|")]
    if len(parts) < 2:
        logger.warning(f"[SMS-WEBHOOK] Invalid format: {message}")
        raise HTTPException(status_code=400, detail="Invalid SMS format — expected NS|... or RS|...")

    # ── 3. Survey Type Detection ──────────────────────────────────────────────
    form_type_code = parts[0].upper()
    if form_type_code == "NS":
        target_survey_type = SurveyType.NATIONAL.value
    elif form_type_code == "RS":
        target_survey_type = SurveyType.REGIONAL.value
    else:
        logger.warning(f"[SMS-WEBHOOK] Unknown type code '{form_type_code}'")
        raise HTTPException(status_code=400, detail=f"Unknown survey type: '{form_type_code}'. Expected NS or RS.")

    # ── 4. Resolve Agent via Phone Number ─────────────────────────────────────
    clean_sender = phone_number.strip().replace(" ", "").replace("-", "")
    suffix = clean_sender[-9:] if len(clean_sender) >= 9 else clean_sender

    agent = db.query(User).filter(
        User.phone.like(f"%{suffix}%"),
        User.is_active == True,
        User.is_deleted == False
    ).first()

    if not agent:
        logger.error(f"[SMS-WEBHOOK] Agent not found | sender={phone_number} | suffix={suffix}")
        _log_inbound_sms(db, phone_number, message, received_at, "failed_no_agent")
        db.commit()
        raise HTTPException(
            status_code=404,
            detail="Agent not found — sender phone number is not registered in the system"
        )

    logger.info(f"[SMS-WEBHOOK] Resolved agent: id={agent.id} | name={agent.full_name}")

    # ── 5. Find Active Survey ─────────────────────────────────────────────────
    survey = db.query(Survey).filter(
        Survey.form_type == target_survey_type,
        Survey.status == SurveyStatus.ACTIVE.value
    ).first()

    if not survey:
        logger.error(f"[SMS-WEBHOOK] No active {target_survey_type} survey found")
        _log_inbound_sms(db, phone_number, message, received_at, "failed_no_survey", agent_id=agent.id)
        db.commit()
        raise HTTPException(status_code=404, detail=f"No active survey found for type: {target_survey_type}")

    logger.info(f"[SMS-WEBHOOK] Matched survey: id={survey.id} | name={survey.name}")

    # ── 6. Parse SMS Fields ───────────────────────────────────────────────────
    total_farmers = 0
    participating_farmers = 0
    spoiled_responses = 0
    parsed_crops = []
    sms_agent_name = "Unknown"
    sms_region_name = "Unknown"

    for part in parts[1:]:
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        key = key.strip()
        val = val.strip()

        try:
            if key == "Ag":
                sms_agent_name = val
            elif key == "Reg":
                sms_region_name = val
            elif key == "TF":
                total_farmers = int(val)
            elif key == "PF":
                participating_farmers = int(val)
            elif key == "SR":
                spoiled_responses = int(val)
            else:
                yield_val = float(val)
                crop_name = key
                crop_id = None
                family_name = "Unknown"

                CropModel = NationalCrop if form_type_code == "NS" else RegionalCrop
                crop = db.query(CropModel).filter(
                    CropModel.crop_name.ilike(f"{key}%")
                ).first()

                if crop:
                    crop_name = crop.crop_name
                    crop_id = crop.id
                    family_name = crop.family.family_name if crop.family else "Unknown"
                    logger.info(f"[SMS-WEBHOOK] Crop '{key}' → '{crop_name}' (id={crop_id}, family={family_name})")
                else:
                    logger.warning(f"[SMS-WEBHOOK] Crop abbreviation '{key}' not found in DB — stored as-is")

                parsed_crops.append({
                    "crop_id": crop_id,
                    "crop_name": crop_name,
                    "family_name": family_name,
                    "yield_tonnes": yield_val,
                })
        except ValueError:
            logger.warning(f"[SMS-WEBHOOK] Skipping unparseable part: '{part}'")
            continue

    logger.info(
        f"[SMS-WEBHOOK] Parsed | TF={total_farmers} PF={participating_farmers} "
        f"SR={spoiled_responses} crops={len(parsed_crops)} | "
        f"sms_agent={sms_agent_name} sms_region={sms_region_name}"
    )

    # ── 7. Build survey_data JSON (stored on Report) ──────────────────────────
    survey_data = {
        "total_farmers": total_farmers,
        "participating_farmers": participating_farmers,
        "spoiled_responses": spoiled_responses,
        "crops": parsed_crops,
        "source": "sms_gateway",
        "sms_agent_name": sms_agent_name,
        "sms_region_name": sms_region_name,
        "gateway_received_at": submission_time.isoformat(),
    }

    # ── 8. Build description label ────────────────────────────────────────────
    description = f"SMS Gateway submission on {received_at} | Sender: {phone_number}"

    # ── 9. Save or Overwrite Report (Duplicate Prevention) ───────────────────
    existing_report = db.query(Report).filter(
        Report.agent_id == agent.id,
        Report.survey_id == survey.id
    ).first()

    if existing_report:
        existing_report.title = f"SMS Submission: {survey.name}"
        existing_report.description = description
        existing_report.survey_data = json.dumps(survey_data)
        existing_report.status = ReportStatus.PENDING
        action_msg = "Updated existing report via SMS"
        logger.info(f"[SMS-WEBHOOK] Overwrote existing report id={existing_report.id}")
    else:
        new_report = Report(
            agent_id=agent.id,
            survey_id=survey.id,
            title=f"SMS Submission: {survey.name}",
            description=description,
            status=ReportStatus.PENDING,
            gps_lat=agent.last_lat or 0.0,
            gps_lng=agent.last_lng or 0.0,
            province_id=agent.province_id,
            district_id=agent.district_id,
            region_id=agent.region_id,
            camp_id=agent.camp_id,
            survey_data=json.dumps(survey_data),
        )
        db.add(new_report)
        action_msg = "Created new report via SMS"
        logger.info(f"[SMS-WEBHOOK] Created new report for agent id={agent.id}")

    # ── 10. Audit Log of inbound SMS ─────────────────────────────────────────
    _log_inbound_sms(db, phone_number, message, received_at, "processed", agent_id=agent.id)

    db.commit()
    logger.info(f"[SMS-WEBHOOK] Complete — {action_msg}")

    return {
        "status": "success",
        "message": action_msg,
        "parsed_crops_count": len(parsed_crops),
        "agent": agent.full_name,
        "survey": survey.name,
        "received_at": received_at,
    }

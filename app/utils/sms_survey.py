def convert_report_to_sms(report_data: dict, title: str, agent_name: str = "Agent", region_name: str = "N/A") -> str:
    """
    Converts report/survey data into a compact 160-character SMS text (spec requirement).
    Target format: NS|Ag:{Agent}|Reg:{Region}|TF:{Total}|PF:{Participating}|SR:{Spoiled}|Wh:{Yield}|Rc:{Yield}
    """
    if not report_data:
        return "NS" + "|Ag:" + (agent_name[:8] or "Agent")

    parts = []
    # Use "NS" or "RS" based on title
    if "regional" in title.lower():
        parts.append("RS")
    else:
        parts.append("NS")

    parts.append(f"Ag:{str(agent_name)[:10].replace(' ', '') or 'Agent'}")
    parts.append(f"Reg:{str(region_name)[:10].replace(' ', '')}")

    tf = report_data.get("total_farmers") or report_data.get("total_farmers_region") or 0
    pf = report_data.get("participating_farmers") or report_data.get("participating_farmers_region") or 0
    sr = report_data.get("spoiled_responses") or 0
    parts.append(f"TF:{tf}")
    parts.append(f"PF:{pf}")
    parts.append(f"SR:{sr}")

    crops = report_data.get("crops") or []
    if isinstance(crops, list) and crops:
        crop_parts = []
        for c in crops[:15]:  # limit to avoid overflow
            # Use 2 characters for crop name as per example: Wh for Wheat, Rc for Rice
            name = (c.get("crop_name") or c.get("name") or "")[:2].title().replace(" ", "")
            y = c.get("yield_tonnes") or c.get("yield") or 0
            try:
                y = int(float(y)) if float(y) == int(float(y)) else round(float(y), 1)
            except (TypeError, ValueError):
                y = 0
            if name:
                crop_parts.append(f"{name}:{y}")
        if crop_parts:
            parts.append("|".join(crop_parts)[:80])
    elif isinstance(report_data.get("crops"), dict):
        crop_parts = []
        for k, v in list(report_data["crops"].items())[:8]:
            crop_parts.append(f"{str(k)[:2].title()}:{v}")
        if crop_parts:
            parts.append("|".join(crop_parts)[:80])

    sms_text = "|".join(parts)
    if len(sms_text) > 160:
        sms_text = sms_text[:157] + "..."
    return sms_text

def convert_survey_to_sms(survey_data: dict, survey_name: str) -> str:
    return convert_report_to_sms(survey_data, survey_name)

def send_survey_sms(sms_text: str, db_session):
    """
    Send an SMS for survey submission.

    Resolution of target number (in priority order):
    1. System configuration 'sms_settings' with key 'survey_number'.
    2. Active System Super Admin's phone.
    3. DEFAULT_ADMIN_SMS environment variable (fallback).
    """
    from app.models.user import User, UserRole, NotificationLog, SystemConfiguration
    import os
    import json
    
    # 1. Try system configuration first
    target_number = None
    recipient_id = None

    config = db_session.query(SystemConfiguration).filter(
        SystemConfiguration.key == "sms_settings"
    ).first()
    if config:
        try:
            cfg = json.loads(config.value)
            # Expect something like {"survey_number": "+234..."}
            survey_number = cfg.get("survey_number") or cfg.get("default_number")
            if survey_number:
                target_number = survey_number
                print(f"DEBUG: Using configured survey SMS number from SystemConfiguration: {target_number}")
        except Exception as e:
            print(f"DEBUG: Failed to parse sms_settings configuration: {e}")
    
    # 2. Fallback to Super Admin phone if no configured number
    if not target_number:
        admin_user = db_session.query(User).filter(
            User.role == UserRole.SUPER_ADMIN,
            User.is_active == True,
            User.is_deleted == False
        ).order_by(User.id.asc()).first()
        
        if admin_user and admin_user.phone:
            target_number = admin_user.phone
            recipient_id = admin_user.id
            print(f"DEBUG: Using Super Admin '{admin_user.full_name}' phone number from profile: {target_number}")
        else:
            print("DEBUG: No active System Super Admin with a phone number found.")
    
    # 3. Final fallback to environment variable
    if not target_number:
        target_number = os.getenv("DEFAULT_ADMIN_SMS", "+1234567890")
        print(f"DEBUG: Using env fallback DEFAULT_ADMIN_SMS: {target_number}")
    
    if recipient_id is None:
        # If we didn't resolve a real user via super admin check, try to find any admin
        any_admin = db_session.query(User).filter(
            User.is_active == True,
            User.is_deleted == False
        ).order_by(User.id.asc()).first()
        recipient_id = any_admin.id if any_admin else 1
    
    print(f"DEBUG: Processing SMS TO {target_number}: {sms_text}")
    
    # Send real SMS using Twilio if configured
    from app.core.config import settings
    sms_sent_real = False
    
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER:
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            message = client.messages.create(
                body=sms_text,
                from_=settings.TWILIO_FROM_NUMBER,
                to=target_number
            )
            print(f"DEBUG: Real SMS sent via Twilio. SID: {message.sid}")
            sms_sent_real = True
        except Exception as e:
            print(f"DEBUG: Twilio SMS failed: {str(e)}")
    else:
        print("DEBUG: Twilio not configured. Simulating SMS sending.")
    
    # Log the notification status
    log = NotificationLog(
        recipient_id=recipient_id,
        type="sms",
        message=f"TO {target_number}: {sms_text}",
        status="sent" if sms_sent_real else "simulated"
    )
    db_session.add(log)
    db_session.commit()
    
    return True

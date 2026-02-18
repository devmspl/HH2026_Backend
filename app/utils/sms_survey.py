def convert_report_to_sms(report_data: dict, title: str, agent_name: str = "Agent") -> str:
    """
    Converts report/survey data into a compact 160-character SMS text.

    Example output (aligned with client spec):
    NAT;PF:200;TF:250;SR:5;MAIZ:10T;RICE:5T
    """
    parts = []

    # Prefix with a short title marker (e.g. NAT / REG) and agent name
    prefix = title[:3].upper()
    parts.append(prefix)
    parts.append(f"BY:{agent_name[:10]}")
    
    if report_data:
        for key, value in report_data.items():
            short_key = key[:4].upper()
            parts.append(f"{short_key}:{value}")
    
    sms_text = ";".join(parts)
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
        # If we didn't resolve a real user, fall back to 1 for logging
        recipient_id = 1
    
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

def convert_report_to_sms(report_data: dict, title: str, agent_name: str = "Agent") -> str:
    """
    Converts report/survey data into a compact 160-character SMS text.
    """
    sms_parts = [f"REP: {title[:20]}", f"BY: {agent_name[:10]}"]
    
    if report_data:
        for key, value in report_data.items():
            short_key = key[:4].upper()
            sms_parts.append(f"{short_key}:{value}")
    
    sms_text = " ".join(sms_parts)
    if len(sms_text) > 160:
        sms_text = sms_text[:157] + "..."
    return sms_text

def convert_survey_to_sms(survey_data: dict, survey_name: str) -> str:
    return convert_report_to_sms(survey_data, survey_name)

def send_survey_sms(sms_text: str, db_session):
    """
    Simulates sending an SMS to the System Super Admin's phone number.
    """
    from app.models.user import User, UserRole, NotificationLog
    import os
    
    # Get System Super Admin user(s)
    admin_user = db_session.query(User).filter(
        User.role == UserRole.SUPER_ADMIN,
        User.is_active == True,
        User.is_deleted == False
    ).order_by(User.id.asc()).first()
    
    target_number = os.getenv("DEFAULT_ADMIN_SMS", "+1234567890")
    recipient_id = 1 # Fallback
    
    if admin_user and admin_user.phone:
        target_number = admin_user.phone
        recipient_id = admin_user.id
        print(f"DEBUG: Using Super Admin '{admin_user.full_name}' phone number from profile: {target_number}")
    else:
        print(f"DEBUG: No active System Super Admin with a phone number found. Using env fallback: {target_number}")
    
    print(f"DEBUG: Processing SMS TO {target_number}: {sms_text}")
    
    # 3. Send real SMS using Twilio if configured
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

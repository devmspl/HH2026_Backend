import sys
import os
import json
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import SystemConfiguration

db = SessionLocal()
config = db.query(SystemConfiguration).filter(SystemConfiguration.key == "sms_settings").first()

if config:
    print(f"Key: {config.key}")
    print(f"Value: {config.value}")
    try:
        val = json.loads(config.value)
        print(f"Parsed Value: {val}")
        print(f"Survey Number: {val.get('survey_number')}")
    except Exception as e:
        print(f"JSON Parse Error: {e}")
else:
    print("No sms_settings found in SystemConfiguration.")

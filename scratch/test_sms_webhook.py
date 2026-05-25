import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# We need an agent with a phone number in the DB to test this.
# Let's see if we can find one first.
from app.db.session import SessionLocal
from app.models.user import User, Survey, SurveyStatus
db = SessionLocal()
agent = db.query(User).filter(User.phone != None, User.is_active == True).first()

if not agent:
    print("No agent with a phone number found for testing.")
    sys.exit(0)

# Check for active survey
survey = db.query(Survey).filter(Survey.status == SurveyStatus.ACTIVE.value).first()
if not survey:
    print("No active survey found. Cannot test webhook.")
    sys.exit(0)

print(f"Testing with Agent: {agent.full_name}, Phone: {agent.phone}")
print(f"Target Survey: {survey.name}, Type: {survey.form_type}")

form_type_code = "NS" if "National" in survey.form_type else "RS"
payload = {
    "sender": agent.phone,
    "message": f"{form_type_code}|Ag:Test|Reg:Test|TF:100|PF:80|SR:2|Ma:10.5|Wh:8.0",
    "timestamp": "2023-10-25T10:00:00Z"
}

response = client.post("/api/v1/sms-webhook/receive", json=payload)
print(f"Response Code: {response.status_code}")
print(f"Response Body: {response.json()}")

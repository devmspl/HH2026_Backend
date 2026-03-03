from app.db.session import SessionLocal
from app.models.user import RegionalCrop, Report, Survey
import json

def check_data():
    db = SessionLocal()
    try:
        print("--- Regional Crops in DB ---")
        crops = db.query(RegionalCrop).all()
        for c in crops:
            print(f"Name: '{c.crop_name}', ID: '{c.rcrop_id}'")
            
        print("\n--- Reports Survey Data ---")
        reports = db.query(Report).all()
        for r in reports:
            if not r.survey_data: continue
            data = json.loads(r.survey_data)
            print(f"Report ID: {r.id}, Survey ID: {r.survey_id}")
            for crop in data.get("crops", []):
                print(f"  Crop in Report: '{crop.get('crop_name')}', Family: '{crop.get('family_name')}', ID in Report: '{crop.get('rcrop_id')}'")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_data()

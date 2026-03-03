from app.db.session import SessionLocal
from app.models.user import Report, Survey, NationalCrop
from app.api.v1.endpoints.reports import _aggregate_national_crop_reports
import json

def test_aggregation():
    db = SessionLocal()
    try:
        query = (
            db.query(Report)
            .join(Survey, Report.survey_id == Survey.id)
            .filter(
                (Survey.form_type == "National Crops Survey") | (Survey.form_type == "Regional Crops Survey")
            )
        )
        reports = query.all()
        print(f"Total reports found for survey: {len(reports)}")
        
        crops_info = db.query(NationalCrop.crop_name, NationalCrop.crop_id).all()
        id_map = {c.crop_name: c.crop_id for c in crops_info if c.crop_id}
        print(f"Map: {id_map}")

        total_farmers, participating_farmers, spoiled_responses, rows, families = _aggregate_national_crop_reports(reports, id_map)
        
        print(f"Agg Result - Farmers: {total_farmers}, Participating: {participating_farmers}")
        print(f"Rows ({len(rows)}):")
        for r in rows:
            print(f"  Crop: {r.crop_name}, ID: {r.crop_id}, Yield: {r.yield_tonnes}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_aggregation()

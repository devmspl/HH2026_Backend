import json
import os
from sqlalchemy import create_engine, text
from app.core.config import settings

def update_mock_data():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        provinces = conn.execute(text("SELECT id, name FROM provinces")).fetchall()
        
        # We will make these provinces dominated by different families
        # so the map shows different colors.
        target_families = {
            "COPPERBELT": "Tubers",
            "EASTERN": "Legumes",
            "LUSAKA": "Fruits",
            "NORTHERN": "Vegetables",
            "SOUTHERN": "Cash Crops" # fallback if needed, but we don't have it in table. Let's use Legumes again.
        }
        
        for prov_id, prov_name in provinces:
            family_to_boost = target_families.get(prov_name)
            if not family_to_boost:
                continue
                
            # Get one approved report in this province
            report = conn.execute(
                text("SELECT id, survey_data FROM reports WHERE province_id = :p_id AND status = 'APPROVED' LIMIT 1"),
                {"p_id": prov_id}
            ).fetchone()
            
            if report:
                report_id = report[0]
                survey_data_str = report[1]
                
                try:
                    survey_data = json.loads(survey_data_str) if survey_data_str else {"crops": []}
                    if "crops" not in survey_data:
                        survey_data["crops"] = []
                    
                    # Add a massive yield for the target family to ensure it dominates
                    survey_data["crops"].append({
                        "crop_name": f"Mock {family_to_boost}",
                        "family_name": family_to_boost,
                        "yield_tonnes": 90000.0  # Massive yield to dominate
                    })
                    
                    # Update DB
                    conn.execute(
                        text("UPDATE reports SET survey_data = :data WHERE id = :id"),
                        {"data": json.dumps(survey_data), "id": report_id}
                    )
                    conn.commit()
                    print(f"Boosted {family_to_boost} in {prov_name} (Report ID: {report_id})")
                except Exception as e:
                    print(f"Error parsing json for report {report_id}: {e}")

if __name__ == "__main__":
    update_mock_data()

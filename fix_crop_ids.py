from app.db.session import SessionLocal
from app.models.user import NationalCrop, RegionalCrop, CropFamily
from sqlalchemy.orm import Session

def fix_missing_ids():
    db = SessionLocal()
    try:
        # 1. Fix NationalCrops
        crops = db.query(NationalCrop).all()
        families = {f.id: f.family_name for f in db.query(CropFamily).all()}
        
        print(f"Checking {len(crops)} National Crops...")
        count_n = 0
        for i, c in enumerate(crops):
            if not c.crop_id:
                f_name = families.get(c.family_id, "UNK")
                c.crop_id = f"NC-{f_name[:1].upper()}{i+1:03d}"
                count_n += 1
        
        # 2. Fix RegionalCrops
        r_crops = db.query(RegionalCrop).all()
        print(f"Checking {len(r_crops)} Regional Crops...")
        count_r = 0
        for i, rc in enumerate(r_crops):
            if not rc.rcrop_id:
                rc.rcrop_id = f"RC-{rc.region_id or 0:02d}-{i+1:03d}"
                count_r += 1
        
        db.commit()
        print(f"Successfully updated {count_n} National Crops and {count_r} Regional Crops with IDs.")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_missing_ids()

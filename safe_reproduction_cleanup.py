from app.db.session import SessionLocal
from app.models.user import User, Province, District, Region, Camp, UserRole
from sqlalchemy import text

def safe_cleanup():
    db = SessionLocal()
    try:
        print("--- Starting SUPER AGGRESSIVE SAFE Deep Cleanup ---")
        
        # Target roles
        target_roles = [UserRole.DISTRICT, UserRole.REGION, UserRole.CAMP, UserRole.AGENT]
        
        # Wipe all child tables first
        tables_to_wipe = [
            "regional_crops", "customers", "audit_logs", "notification_logs", 
            "chat_messages", "survey_targets", "report_media", "reports"
        ]
        
        for table in tables_to_wipe:
            print(f"Wiping {table}...")
            db.execute(text(f"DELETE FROM {table}"))
        
        # Unset parent_id
        db.execute(text("UPDATE users SET parent_id = NULL WHERE role IN ('DISTRICT', 'REGION', 'CAMP', 'AGENT')"))
        
        # Delete Users
        deleted_users_count = db.query(User).filter(User.role.in_(target_roles)).delete(synchronize_session=False)
        print(f"Deleted {deleted_users_count} users with restricted roles.")

        # Wipe Locations
        for table in ["camps", "regions", "districts"]:
            print(f"Wiping {table}...")
            db.execute(text(f"DELETE FROM {table}"))
        
        # Nullify location IDs for remaining users
        db.execute(text("UPDATE users SET province_id = NULL, district_id = NULL, region_id = NULL, camp_id = NULL"))
        
        print("Wiping provinces...")
        db.execute(text("DELETE FROM provinces"))

        db.commit()
        print("--- Cleanup SUCCESS: System is now 100% CLEAN ---")
        
    except Exception as e:
        db.rollback()
        print(f"CRITICAL ERROR during cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    safe_cleanup()

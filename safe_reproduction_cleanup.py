from app.db.session import SessionLocal
from app.models.user import User, Province, District, Region, Camp, UserRole
from sqlalchemy import text

def safe_cleanup():
    db = SessionLocal()
    try:
        print("--- Starting FINAL FIXED SERVER Cleanup ---")
        
        # Target roles for deletion
        target_roles = [UserRole.DISTRICT, UserRole.REGION, UserRole.CAMP, UserRole.AGENT]
        
        # 1. Wipe child tables
        tables_to_wipe = [
            "chat_group_members", "chat_messages", "chat_groups",
            "regional_crops", "customers", "audit_logs", "notification_logs", 
            "survey_targets", "report_media", "reports"
        ]
        
        for table in tables_to_wipe:
            print(f"Wiping {table}...")
            db.execute(text(f"DELETE FROM {table}"))
        
        # 2. IMPORTANT: Nullify ALL location links for ALL users BEFORE deleting locations
        print("Unlinking locations from all users...")
        db.execute(text("UPDATE users SET province_id = NULL, district_id = NULL, region_id = NULL, camp_id = NULL, parent_id = NULL"))
        
        # 3. Delete Users with target roles
        deleted_users_count = db.query(User).filter(User.role.in_(target_roles)).delete(synchronize_session=False)
        print(f"Deleted {deleted_users_count} users with restricted roles.")

        # 4. Wipe Locations (Order: Camp -> Region -> District -> Province)
        for table in ["camps", "regions", "districts", "provinces"]:
            print(f"Wiping {table}...")
            db.execute(text(f"DELETE FROM {table}"))

        db.commit()
        print("--- Cleanup SUCCESS: System is now 100% CLEAN ---")
        
    except Exception as e:
        db.rollback()
        print(f"CRITICAL ERROR during cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    safe_cleanup()

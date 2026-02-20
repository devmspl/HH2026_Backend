"""
Database reset: sirf Super Admin bachega, baaki sab delete.
Run (backend folder me): python reset_keep_superadmin_only.py
  Windows PowerShell: python reset_keep_superadmin_only.py

- Super Admin = .env me jo FIRST_SUPERUSER email hai, usse login wala user.
- Sab users (agents, camp, region, etc.) delete except that one.
- Reports, customers, chat, notification logs, audit logs, SURVEYS sab delete.
- Reh jayenge: locations (provinces, districts, regions, camps), crops, system config.
  Surveys bhi delete ho jayenge – aap phir se Survey Creation se naye create kar lena.
"""
from sqlalchemy import text
from app.db.session import SessionLocal
from app.core.config import settings

def get_superadmin_id(db):
    """Pehla SUPER_ADMIN: pehle FIRST_SUPERUSER email se, nahi to koi bhi SUPER_ADMIN."""
    r = db.execute(
        text("SELECT id FROM users WHERE email = :email AND role = 'SUPER_ADMIN' LIMIT 1"),
        {"email": str(settings.FIRST_SUPERUSER)}
    ).first()
    if r:
        return r[0]
    r = db.execute(text("SELECT id FROM users WHERE role = 'SUPER_ADMIN' LIMIT 1")).first()
    return r[0] if r else None

def run():
    db = SessionLocal()
    try:
        superadmin_id = get_superadmin_id(db)
        if not superadmin_id:
            print("ERROR: Super Admin nahi mila. .env me FIRST_SUPERUSER check karo aur pehle seed_db.py / migrate se superuser bana lo.")
            return

        print(f"Super Admin ID: {superadmin_id} (email: {settings.FIRST_SUPERUSER})")
        print("Deleting all data except this user...")

        # Order: child tables pehle, phir parent. Users last.
        db.execute(text("DELETE FROM report_media"))
        try:
            db.execute(text("DELETE FROM report_images"))
        except Exception:
            pass
        db.execute(text("DELETE FROM report_edit_history"))
        db.execute(text("DELETE FROM reports"))
        db.execute(text("DELETE FROM notification_logs"))
        db.execute(text("DELETE FROM audit_logs"))
        db.execute(text("DELETE FROM chat_messages"))
        db.execute(text("DELETE FROM chat_group_members"))
        db.execute(text("DELETE FROM chat_groups"))
        db.execute(text("DELETE FROM survey_targets"))
        db.execute(text("DELETE FROM surveys"))
        db.execute(text("DELETE FROM customers"))

        db.execute(text("DELETE FROM users WHERE id != :sid"), {"sid": superadmin_id})

        db.commit()
        print("Done. Sirf Super Admin reh gaya. Surveys bhi delete ho gaye. Ab aap login karke naye agents, surveys, customers sab fir se create kar sakte ho.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    run()

# cleanup_server.py
from app.db.session import SessionLocal
from app.models.user import User, UserRole, Report, Customer, ReportMedia

def run_cleanup():
    db = SessionLocal()
    try:
        # 1. Identify users to remove
        roles_to_remove = [UserRole.AGENT, UserRole.DISTRICT, UserRole.REGION, UserRole.CAMP]
        users = db.query(User).filter(User.role.in_(roles_to_remove)).all()
        user_ids = [u.id for u in users]
        
        if not user_ids:
            print("No users found for the specified roles.")
            return

        print(f"Found {len(user_ids)} users. Removing associated data...")

        # 2. Delete Report Media (ForeignKey to Reports)
        report_ids = [r.id for r in db.query(Report.id).filter(Report.agent_id.in_(user_ids)).all()]
        if report_ids:
            db.query(ReportMedia).filter(ReportMedia.report_id.in_(report_ids)).delete(synchronize_session=False)
            print(f"Deleted media for {len(report_ids)} reports.")

        # 3. Delete Reports
        db.query(Report).filter(Report.agent_id.in_(user_ids)).delete(synchronize_session=False)
        print("Deleted reports.")

        # 4. Unassign Customers
        db.query(Customer).filter(Customer.assigned_camp_user_id.in_(user_ids)).update(
            {Customer.assigned_camp_user_id: None}, synchronize_session=False
        )
        print("Unassigned customers.")

        # 5. Delete Users
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        
        db.commit()
        print("Cleanup Success: All restricted roles and associated data removed.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_cleanup()

from app.db.session import SessionLocal
from app.models.user import User, UserRole, Report, Customer, ReportMedia, NotificationLog, AuditLog, ChatMessage, chat_group_members, ChatGroup, survey_targets, ReportEditHistory
from sqlalchemy import delete

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

        print(f"Found {len(user_ids)} users. Removing all dependencies...")

        # 2. Delete Dependencies in correct order
        # A. Notification Logs
        db.query(NotificationLog).filter((NotificationLog.recipient_id.in_(user_ids)) | (NotificationLog.sender_id.in_(user_ids))).delete(synchronize_session=False)
        
        # B. Audit Logs
        db.query(AuditLog).filter(AuditLog.user_id.in_(user_ids)).delete(synchronize_session=False)

        # C. Chat Messages & Group Members
        db.query(ChatMessage).filter(ChatMessage.sender_id.in_(user_ids)).delete(synchronize_session=False)
        db.execute(delete(chat_group_members).where(chat_group_members.c.user_id.in_(user_ids)))
        
        # D. Survey Targets
        db.execute(delete(survey_targets).where(survey_targets.c.user_id.in_(user_ids)))

        # E. Reports & Media
        report_ids = [r.id for r in db.query(Report.id).filter(Report.agent_id.in_(user_ids)).all()]
        if report_ids:
            db.query(ReportMedia).filter(ReportMedia.report_id.in_(report_ids)).delete(synchronize_session=False)
            db.query(ReportEditHistory).filter(ReportEditHistory.report_id.in_(report_ids)).delete(synchronize_session=False)
            db.query(Report).filter(Report.id.in_(report_ids)).delete(synchronize_session=False)

        # F. Handle Chat Groups managed by these users
        db.query(ChatGroup).filter(ChatGroup.manager_id.in_(user_ids)).delete(synchronize_session=False)

        # 3. Unassign Customers
        db.query(Customer).filter((Customer.assigned_camp_user_id.in_(user_ids)) | (Customer.agent_id.in_(user_ids))).update(
            {Customer.assigned_camp_user_id: None, Customer.agent_id: None}, synchronize_session=False
        )

        # 4. Finally Delete Users
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        
        db.commit()
        print("Cleanup Success: All restricted roles and associated data removed safely.")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_cleanup()

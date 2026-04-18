import json
from app.db.session import SessionLocal
from app.models.user import User, SystemRole, Report, Customer, ChatGroup, chat_group_members
from sqlalchemy import func

def generate_user_audit_report(output_file="user_audit_report.txt"):
    db = SessionLocal()
    report_lines = []
    
    def rprint(text):
        print(text)
        report_lines.append(text)

    try:
        # Fetch all active users with their system roles
        users = db.query(User).filter(User.is_deleted == False).order_by(User.role).all()
        
        rprint("\n" + "="*100)
        rprint(f"{'USER PERMISSIONS & DATA AUDIT REPORT':^100}")
        rprint("="*100 + "\n")

        for user in users:
            rprint(f"User: {user.full_name or 'N/A'} (ID: {user.id})")
            rprint(f"Email: {user.email}")
            
            # Role Information
            role_name = user.role
            system_role_name = user.system_role.name if user.system_role else "N/A"
            rprint(f"Role (Type): {role_name}")
            rprint(f"System Role: {system_role_name}")
            
            # Permissions
            role_perms = user.system_role.permissions if user.system_role else None
            user_perms = user.permissions if user.permissions else None
            
            rprint(f"--- Permissions ---")
            
            # Handle Role Permissions
            if role_perms:
                try:
                    rp = json.loads(role_perms) if isinstance(role_perms, str) else role_perms
                    rprint(f"  Role Permissions: {json.dumps(rp, indent=2)}")
                except:
                    rprint(f"  Role Permissions (Raw): {role_perms}")
            else:
                rprint("  Role Permissions: None defined in system role")
                
            # Handle Individual Permissions
            if user_perms:
                try:
                    up = json.loads(user_perms) if isinstance(user_perms, str) else user_perms
                    rprint(f"  Individual User Permissions: {json.dumps(up, indent=2)}")
                except:
                    rprint(f"  Individual User Permissions (Raw): {user_perms}")
            else:
                rprint(f"  Individual User Permissions: None set")

            # Related Data Summary
            reports_count = db.query(func.count(Report.id)).filter(Report.agent_id == user.id).scalar()
            
            # Customers assigned to this user
            customers_count = db.query(func.count(Customer.id)).filter(
                (Customer.agent_id == user.id) | (Customer.assigned_camp_user_id == user.id)
            ).scalar()
            
            # Chat groups count
            chat_groups_count = db.query(func.count(chat_group_members.c.group_id)).filter(
                chat_group_members.c.user_id == user.id
            ).scalar()

            # Subordinates count
            subordinates_count = db.query(func.count(User.id)).filter(User.parent_id == user.id).scalar()

            rprint(f"--- Related Data Summary ---")
            rprint(f"  Reports Submitted: {reports_count}")
            rprint(f"  Customers Assigned: {customers_count}")
            rprint(f"  Chat Groups Joined: {chat_groups_count}")
            rprint(f"  Direct Reports (Subordinates): {subordinates_count}")
            rprint(f"  Location Info: Camp ID: {user.camp_id}, Region ID: {user.region_id}, Province ID: {user.province_id}")
            
            rprint("-" * 50 + "\n")

        with open(output_file, "w") as f:
            f.write("\n".join(report_lines))
        print(f"\nFull report saved to: {output_file}")

    except Exception as e:
        print(f"Error generating report: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    generate_user_audit_report()

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User, UserRole, Report, ReportStatus, ChatGroup, ChatMessage
from datetime import datetime
import random

def seed_data():
    db = SessionLocal()
    try:
        # 1. Get existing agents
        agents = db.query(User).filter(User.role == UserRole.AGENT).all()
        if not agents:
            print("No agents found. Please create some agents first.")
            return

        print(f"Seeding reports for {len(agents)} agents...")
        
        # 2. Seed Reports
        titles = [
            "Site Survey - Sector 14", "Inventory Audit - Warehouse A", 
            "Customer Feedback - Civil Lines", "Field Visit - Connaught Place",
            "Asset Verification - North Zone", "New Enrollment - DLF Phase 3"
        ]
        descriptions = [
            "Everything looks good. All parameters verified.",
            "Stock levels are slightly low. Recommended reorder.",
            "Customer was satisfied with the service. Requested follow-up.",
            "Site is ready for deployment. GPS coordinates marked.",
            "Verification completed. No missing assets found.",
            "Enrolled 5 new customers. Documentation attached."
        ]

        for agent in agents:
            # Create 2 reports for each agent
            for _ in range(2):
                report = Report(
                    agent_id=agent.id,
                    title=random.choice(titles),
                    description=random.choice(descriptions),
                    status=random.choice([ReportStatus.PENDING, ReportStatus.APPROVED]),
                    gps_lat=agent.last_lat or (28.61 + random.uniform(-0.1, 0.1)),
                    gps_lng=agent.last_lng or (77.23 + random.uniform(-0.1, 0.1)),
                    confirmation_no=f"CONF-{random.randint(10000, 99999)}"
                )
                db.add(report)
        
        # 3. Seed Chat Groups
        print("Seeding chat groups...")
        if db.query(ChatGroup).count() == 0:
            groups_to_create = ["Delhi Field Team", "Urgent Announcements", "Support & Help"]
            for g_name in groups_to_create:
                group = ChatGroup(name=g_name, manager_id=1) # Admin is ID 1
                db.add(group)
            db.commit()

        # 4. Seed Messages
        print("Seeding messages...")
        groups = db.query(ChatGroup).all()
        messages = [
            "Hello team, welcome to the new portal!",
            "Please make sure to upload GPS coordinates for every report.",
            "Anyone available near Sector 10?",
            "I've submitted my daily report. Please verify.",
            "Good morning! Let's hit our targets today."
        ]
        
        for g in groups:
            if db.query(ChatMessage).filter(ChatMessage.group_id == g.id).count() == 0:
                for msg_text in messages:
                    msg = ChatMessage(
                        group_id=g.id,
                        sender_id=random.choice([1] + [a.id for a in agents]),
                        text=msg_text
                    )
                    db.add(msg)
        
        # 5. Seed Notifications
        print("Seeding notifications...")
        from app.models.user import NotificationLog
        notif_messages = [
            "Site Survey - Sector 14 has been approved by Admin.",
            "New agent enrollment: Amit Shah has joined the Delhi Team.",
            "System Alert: Maintenance scheduled for 11:00 PM tonight.",
            "Site Visit report for Warehouse A received 5 minutes ago.",
            "Sync Complete: 1,540 reports synchronized with the main database."
        ]
        
        for msg_text in notif_messages:
            notif = NotificationLog(
                recipient_id=1, # Admin
                type="push",
                message=msg_text,
                status="sent"
            )
            db.add(notif)
        
        db.commit()
        print("Mock data seeded successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    seed_data()

import sys
import os
sys.path.append(os.getcwd())
from app.db.session import SessionLocal
from app.models.user import Report, ReportStatus

db = SessionLocal()
report = db.query(Report).filter(Report.id == 660).first()

if report:
    print(f"Current Status in script: {report.status}")
    report.status = ReportStatus.APPROVED
    db.commit()
    print("Committed status update to APPROVED.")
    
    # Query again in a new session or refresh
    db.refresh(report)
    print(f"Verified Status after refresh: {report.status}")
    
    # Query in a fresh session
    db2 = SessionLocal()
    r2 = db2.query(Report).filter(Report.id == 660).first()
    print(f"Verified Status in fresh session: {r2.status}")
else:
    print("Report not found.")

import sys
sys.path.append('.')
from app.db.session import SessionLocal
from app.models.user import RegionalCrop, NationalCrop, Report, Survey

db = SessionLocal()

print('--- Regional Crops ---')
for c in db.query(RegionalCrop).all():
    print(f'ID: {c.id}, Name: {c.crop_name}, rCrop_id field: {c.rcrop_id}')

print('\n--- National Crops ---')
for c in db.query(NationalCrop).all():
    print(f'ID: {c.id}, Name: {c.crop_name}, crop_id field: {c.crop_id}')

print('\n--- Regional Survey Reports ---')
for r in db.query(Report).join(Survey, Report.survey_id == Survey.id).filter(Survey.form_type == 'Regional Crops Survey').all():
    print(f'Report {r.id}: {r.title}')
    print(f'Survey Data: {r.survey_data}')

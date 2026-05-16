import json
from app.db.session import SessionLocal
from app.models.user import SystemConfiguration

db = SessionLocal()
config = db.query(SystemConfiguration).filter(SystemConfiguration.key == "station_location").first()
if not config:
    config = SystemConfiguration(key="station_location", value=json.dumps({"lat": -13.5, "lng": 28.5}))
    db.add(config)
else:
    config.value = json.dumps({"lat": -13.5, "lng": 28.5})
db.commit()
print("Station location updated successfully.")

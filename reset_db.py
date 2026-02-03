from app.db.base import Base
from app.db.session import engine
import app.models.user # Ensure all models are loaded

def reset_database():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Recreating all tables with new schema...")
    Base.metadata.create_all(bind=engine)
    print("Database reset successfully.")

if __name__ == "__main__":
    reset_database()

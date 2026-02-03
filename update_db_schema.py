import sys
import os

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

from app.db.session import engine
from app.db.base import Base
# Import models so they are registered in Base
from app.models import user

def create_tables():
    print("Creating missing tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    create_tables()

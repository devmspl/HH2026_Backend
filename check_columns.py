from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("DATABASE_URL not found in .env")
    exit(1)

engine = create_engine(db_url)
inspector = inspect(engine)
columns = inspector.get_columns('users')
print("Columns in 'users' table:")
for column in columns:
    print(f"- {column['name']} ({column['type']})")

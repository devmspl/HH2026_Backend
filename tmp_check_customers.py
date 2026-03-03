from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    # try default sqlite if not in env
    db_url = "sqlite:///./app.db"

engine = create_engine(db_url)
inspector = inspect(engine)

def check_table(table_name):
    if not inspector.has_table(table_name):
        print(f"Table '{table_name}' does not exist.")
        return
    columns = inspector.get_columns(table_name)
    print(f"Columns in '{table_name}' table:")
    for column in columns:
        print(f"- {column['name']} ({column['type']})")

check_table('customers')

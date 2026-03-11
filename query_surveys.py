import asyncio
from sqlalchemy import create_engine
from app.db.session import engine
import pandas as pd

def main():
    query = "SELECT id, title, form_type, status FROM surveys"
    df = pd.read_sql(query, engine)
    print(df)

if __name__ == "__main__":
    main()

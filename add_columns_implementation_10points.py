"""
Migration: Add columns for NOT IMPLEMENTED list points 1-10.
Run from backend root: python add_columns_implementation_10points.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

def run():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        def add_col(table, col, sql):
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  OK {table}.{col}")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"  -- {table}.{col} already exists")
                else:
                    print(f"  FAIL {table}.{col}: {e}")

        print("1. Users: camp_id, region_id, province_id, district_id, age, sex, profession, nrc")
        add_col("users", "camp_id", "ALTER TABLE users ADD COLUMN camp_id INTEGER REFERENCES camps(id)")
        add_col("users", "region_id", "ALTER TABLE users ADD COLUMN region_id INTEGER REFERENCES regions(id)")
        add_col("users", "province_id", "ALTER TABLE users ADD COLUMN province_id INTEGER REFERENCES provinces(id)")
        add_col("users", "district_id", "ALTER TABLE users ADD COLUMN district_id INTEGER REFERENCES districts(id)")
        add_col("users", "age", "ALTER TABLE users ADD COLUMN age INTEGER")
        add_col("users", "sex", "ALTER TABLE users ADD COLUMN sex VARCHAR(20)")
        add_col("users", "profession", "ALTER TABLE users ADD COLUMN profession VARCHAR(255)")
        add_col("users", "nrc", "ALTER TABLE users ADD COLUMN nrc VARCHAR(50)")

        print("2. Reports: survey_data (if missing), province_id, district_id, region_id, camp_id")
        add_col("reports", "survey_data", "ALTER TABLE reports ADD COLUMN survey_data TEXT")
        add_col("reports", "province_id", "ALTER TABLE reports ADD COLUMN province_id INTEGER REFERENCES provinces(id)")
        add_col("reports", "district_id", "ALTER TABLE reports ADD COLUMN district_id INTEGER REFERENCES districts(id)")
        add_col("reports", "region_id", "ALTER TABLE reports ADD COLUMN region_id INTEGER REFERENCES regions(id)")
        add_col("reports", "camp_id", "ALTER TABLE reports ADD COLUMN camp_id INTEGER REFERENCES camps(id)")

        print("3. Customers: farmer_id, camp_id, region_id, district_id, province_id, membership_status, agent_id, household, education_level, emp_status, photo")
        add_col("customers", "farmer_id", "ALTER TABLE customers ADD COLUMN farmer_id VARCHAR(50)")
        add_col("customers", "camp_id", "ALTER TABLE customers ADD COLUMN camp_id INTEGER REFERENCES camps(id)")
        add_col("customers", "region_id", "ALTER TABLE customers ADD COLUMN region_id INTEGER REFERENCES regions(id)")
        add_col("customers", "district_id", "ALTER TABLE customers ADD COLUMN district_id INTEGER REFERENCES districts(id)")
        add_col("customers", "province_id", "ALTER TABLE customers ADD COLUMN province_id INTEGER REFERENCES provinces(id)")
        add_col("customers", "membership_status", "ALTER TABLE customers ADD COLUMN membership_status VARCHAR(50)")
        add_col("customers", "agent_id", "ALTER TABLE customers ADD COLUMN agent_id INTEGER REFERENCES users(id)")
        add_col("customers", "household", "ALTER TABLE customers ADD COLUMN household VARCHAR(255)")
        add_col("customers", "education_level", "ALTER TABLE customers ADD COLUMN education_level VARCHAR(100)")
        add_col("customers", "emp_status", "ALTER TABLE customers ADD COLUMN emp_status VARCHAR(100)")
        add_col("customers", "photo", "ALTER TABLE customers ADD COLUMN photo VARCHAR(500)")

    print("\nDone. Points 1-5 (DB) migration complete.")

if __name__ == "__main__":
    run()

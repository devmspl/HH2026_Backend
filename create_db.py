import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

def create_database():
    db_name = os.getenv("POSTGRES_DB", "ccns_customer_180")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "123456789")
    host = os.getenv("POSTGRES_SERVER", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")

    # Connect to default 'postgres' database to create the new one
    con = psycopg2.connect(
        dbname='postgres',
        user=user,
        password=password,
        host=host,
        port=port
    )
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = con.cursor()
    
    # Check if database exists
    cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
    exists = cursor.fetchone()
    
    if not exists:
        print(f"Creating database {db_name}...")
        cursor.execute(f'CREATE DATABASE "{db_name}"')
        print(f"Database {db_name} created successfully.")
    else:
        print(f"Database {db_name} already exists.")
    
    cursor.close()
    con.close()

if __name__ == "__main__":
    create_database()

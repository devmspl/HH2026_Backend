"""
Reset Database Script
Run this to drop and recreate the database with new schema
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Database config
DB_HOST = "localhost"
DB_USER = "postgres"
DB_PASSWORD = "123456789"
DB_NAME = "ccns_customer_180"
DB_PORT = 5432

def reset_database():
    print("Connecting to PostgreSQL...")
    
    # Connect to default 'postgres' database
    conn = psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database="postgres",
        port=DB_PORT
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Terminate all connections to the target database
    print(f"Terminating connections to {DB_NAME}...")
    cursor.execute(f"""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '{DB_NAME}'
        AND pid <> pg_backend_pid();
    """)
    
    # Drop database
    print(f"Dropping database {DB_NAME}...")
    cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME};")
    
    # Create database
    print(f"Creating database {DB_NAME}...")
    cursor.execute(f"CREATE DATABASE {DB_NAME};")
    
    cursor.close()
    conn.close()
    
    print("=" * 50)
    print("Database reset successful!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Restart the backend server")
    print("2. Tables will be created automatically")
    print("3. Login with: admin@example.com / admin123")

if __name__ == "__main__":
    try:
        reset_database()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure PostgreSQL is running!")

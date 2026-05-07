import os
import sys
import logging

# Monkeypatch to bypass hashlib/OpenSSL issues on some Mac environments
try:
    import hashlib
except (ImportError, ValueError):
    pass

# Add the project root to sys.path so 'app' can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text
from app.core.config import settings
from app.db.base import Base
import app.models.user # Import all models to register them with Base

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os

def sync_db_schema():
    # Hardcoded URL as requested
    target_url = "postgresql://postgres:mspl%401234prod@localhost:5432/ccns_customer_180"
    
    if "localhost" not in target_url:
        logger.info(f"[*] TARGETING REMOTE DATABASE: {target_url.split('@')[-1]}")
    else:
        logger.info(f"[*] Targeting Local Database: {target_url}")
        
    engine = create_engine(target_url)
    inspector = inspect(engine)
    
    logger.info("[*] Starting Schema Synchronization (Safe Mode)...")
    
    # 1. Create all missing tables
    # Base.metadata.create_all only creates tables that do NOT exist.
    # It is safe and does not delete any data.
    Base.metadata.create_all(bind=engine)
    logger.info("[+] Missing tables created (if any).")
    
    # 2. Check for missing columns in existing tables
    # We will manually handle some key tables to ensure all columns exist
    with engine.begin() as connection:
        for table_name, table_obj in Base.metadata.tables.items():
            # Get existing columns in the DB
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            
            # Check each column defined in the model
            for column in table_obj.columns:
                if column.name not in existing_columns:
                    logger.info(f"[*] Adding missing column '{column.name}' to table '{table_name}'...")
                    
                    # Determine column type for SQL
                    col_type = str(column.type).upper()
                    
                    # Simplified type mapping for common types
                    if "VARCHAR" in col_type:
                        sql_type = col_type
                    elif "INTEGER" in col_type:
                        sql_type = "INTEGER"
                    elif "BOOLEAN" in col_type:
                        sql_type = "BOOLEAN"
                    elif "FLOAT" in col_type:
                        sql_type = "FLOAT"
                    elif "DATETIME" in col_type or "TIMESTAMP" in col_type:
                        sql_type = "TIMESTAMP WITH TIME ZONE"
                    elif "TEXT" in col_type:
                        sql_type = "TEXT"
                    else:
                        sql_type = "TEXT" # Fallback
                        
                    try:
                        # Construct ALTER TABLE command
                        alter_query = f'ALTER TABLE {table_name} ADD COLUMN {column.name} {sql_type};'
                        connection.execute(text(alter_query))
                        logger.info(f"[+] Successfully added {column.name} to {table_name}")
                    except Exception as e:
                        logger.error(f"[-] Failed to add {column.name} to {table_name}: {str(e)}")

    logger.info("[!] Schema Sync Complete. No data was deleted.")

if __name__ == "__main__":
    sync_db_schema()

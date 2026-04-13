import sys
import os
import logging
from sqlalchemy import create_engine, MetaData, Table, insert, delete, text
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.core.config import settings

# --- CONFIGURATION ---
# You can override these in your .env or directly here for migration
LOCAL_DB_URL = "postgresql://postgres:123456789@localhost:5432/ccns_customer_180"
PROD_DB_URL = "postgresql://postgres:password_here@38.242.230.126:5432/production_db_name"

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("migration_sync.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def sync_databases(dry_run=True):
    logger.info(f"--- Starting Migration (Dry Run: {dry_run}) ---")
    
    local_engine = create_engine(LOCAL_DB_URL)
    prod_engine = create_engine(PROD_DB_URL)
    
    # Reflect metadata from local
    metadata = MetaData()
    metadata.reflect(bind=local_engine)
    
    # Define table order based on relationships (Source of truth: SQLAlchemy Metadata)
    # This ensures we don't hit Foreign Key violations
    sorted_tables = metadata.sorted_tables

    try:
        with prod_engine.connect() as prod_conn:
            with local_engine.connect() as local_conn:
                
                # 1. Start Transaction
                trans = prod_conn.begin()
                try:
                    logger.info("Dropping Foreign Key constraints temporarily for speed (Optional Cleanup)...")
                    # Note: We keep constraints but follow sorted order for safety.
                    
                    if not dry_run:
                        logger.warning("CLEANING PRODUCTION TABLES BEFORE IMPORT...")
                        # Delete in reverse order to respect foreign keys
                        for table in reversed(sorted_tables):
                            prod_conn.execute(table.delete())
                        logger.info("✅ Production tables cleaned.")

                    # 2. Iterate and Copy
                    for table in sorted_tables:
                        logger.info(f"Syncing table: {table.name}...")
                        
                        # Fetch all data from local
                        local_data = local_conn.execute(table.select()).fetchall()
                        column_names = table.columns.keys()
                        
                        if not local_data:
                            logger.info(f"   Skipping {table.name} (Empty)")
                            continue
                        
                        records = [dict(zip(column_names, row)) for row in local_data]
                        
                        if not dry_run:
                            # Use bulk insert for performance
                            prod_conn.execute(insert(table), records)
                            logger.info(f"   ✅ Migrated {len(records)} records to {table.name}")
                        else:
                            logger.info(f"   [DRY RUN] Would migrate {len(records)} records to {table.name}")

                    # 3. Validation Check
                    logger.info("--- Data Validation ---")
                    for table in sorted_tables:
                        local_count = local_conn.execute(text(f"SELECT COUNT(*) FROM {table.name}")).scalar()
                        if not dry_run:
                            prod_count = prod_conn.execute(text(f"SELECT COUNT(*) FROM {table.name}")).scalar()
                            status = "MATCH" if local_count == prod_count else "MISMATCH ⚠️"
                            logger.info(f"{table.name:.<30} Local: {local_count:<5} | Prod: {prod_count:<5} | {status}")
                        else:
                            logger.info(f"{table.name:.<30} Local: {local_count:<5} | Prod: (Pending)")

                    if not dry_run:
                        trans.commit()
                        logger.info("--- 🚀 MIGRATION COMPLETED SUCCESSFULLY ---")
                    else:
                        trans.rollback()
                        logger.info("--- ℹ️ DRY RUN COMPLETED (No changes applied) ---")

                except Exception as e:
                    trans.rollback()
                    logger.error(f"❌ Migration failed during processing: {e}")
                    raise

    except Exception as e:
        logger.error(f"❌ Fatal connection error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Safety Check: Default to Dry Run
    is_live = len(sys.argv) > 1 and sys.argv[1] == "--live"
    
    if not is_live:
        print("\n⚠️  RUNNING IN DRY-RUN MODE. Changes will NOT be saved.")
        print("To apply changes to production, run: python sync_local_to_production.py --live\n")
    else:
        print("\n‼️  WARNING: RUNNING IN LIVE MODE. Production data will be replaced!")
        confirm = input("Are you absolutely sure you want to proceed? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
            
    sync_databases(dry_run=not is_live)

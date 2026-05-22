from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

def update_crop_family_color_schema():
    print(f"Connecting to database at {settings.DATABASE_URL}...")
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            print("Connection successful. Adding color column if not exists...")
            
            # Add column 'color'
            try:
                conn.execute(text("ALTER TABLE crop_families ADD COLUMN color VARCHAR(50) DEFAULT NULL"))
                conn.commit()
                print("✅ Added 'color' column to crop_families table")
            except Exception as e:
                conn.rollback()
                if "already exists" in str(e):
                    print("ℹ️  Column 'color' already exists.")
                else:
                    print(f"⚠️  Skipping color column addition: {e}")
            
            # Seed/backfill default colors
            color_map = {
                "Cereals": "#2ecc71",
                "Grains": "#F59E0B",
                "Legumes": "#3498db",
                "Tubers": "#9b59b6",
                "Vegetables": "#e74c3c",
                "Fruits": "#f39c12",
                "Cash Crops": "#EAB308",
                "Oilseeds": "#D97706",
                "Other": "#95a5a6"
            }
            
            print("Backfilling default colors for existing crop families...")
            for family_name, color in color_map.items():
                try:
                    # Update based on family_name case-insensitively or standard match
                    res = conn.execute(
                        text("UPDATE crop_families SET color = :color WHERE LOWER(family_name) = LOWER(:family_name) AND color IS NULL"),
                        {"color": color, "family_name": family_name}
                    )
                    conn.commit()
                    print(f"✅ Seeded color '{color}' for crop family '{family_name}' (where color was NULL)")
                except Exception as e:
                    conn.rollback()
                    print(f"⚠️  Could not seed color for '{family_name}': {e}")
                    
            print("\nDatabase update completed successfully.")
            
    except Exception as e:
        print(f"\n❌ Fatal Error during schema migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    update_crop_family_color_schema()

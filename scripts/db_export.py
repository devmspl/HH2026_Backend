import os
import subprocess
from datetime import datetime

# Load environment variables manually from .env
def load_env():
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    env_vars[key] = value.strip('"').strip("'")
    return env_vars

def export_database():
    env = load_env()
    
    db_name = env.get("POSTGRES_DB", "ccns_customer_180")
    db_user = env.get("POSTGRES_USER", "postgres")
    db_pass = env.get("POSTGRES_PASSWORD", "123456789")
    db_host = env.get("POSTGRES_SERVER", "localhost")
    db_port = env.get("POSTGRES_PORT", "5432")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"ccns_backup_{timestamp}.sql"
    
    print(f"[*] Starting export of database '{db_name}'...")
    
    # Set PGPASSWORD environment variable for pg_dump
    os.environ["PGPASSWORD"] = db_pass
    
    try:
        command = [
            "pg_dump",
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-d", db_name,
            "-f", output_file,
            "--no-owner",  # Important for importing into a different user/db
            "--no-privileges"
        ]
        
        subprocess.run(command, check=True)
        print(f"[+] Export successful! File saved as: {output_file}")
        print("\n[!] TO IMPORT ON SERVER:")
        print(f"1. Upload '{output_file}' to your server.")
        print(f"2. Run: psql -h YOUR_SERVER_HOST -U YOUR_SERVER_USER -d YOUR_SERVER_DB -f {output_file}")
        
    except subprocess.CalledProcessError as e:
        print(f"[-] Export failed: {e}")
    except FileNotFoundError:
        print("[-] Error: 'pg_dump' command not found. Please ensure PostgreSQL client tools are installed.")

if __name__ == "__main__":
    export_database()

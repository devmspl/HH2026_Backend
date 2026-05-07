import os
import subprocess
import sys

# Load environment variables manually from .env
def load_env():
    env_vars = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    parts = line.strip().split("=", 1)
                    if len(parts) == 2:
                        key, value = parts
                        env_vars[key] = value.strip('"').strip("'")
    return env_vars

def import_database(sql_file):
    env = load_env()
    
    db_name = env.get("POSTGRES_DB", "ccns_customer_180")
    db_user = env.get("POSTGRES_USER", "postgres")
    db_pass = env.get("POSTGRES_PASSWORD", "123456789")
    db_host = env.get("POSTGRES_SERVER", "localhost")
    db_port = env.get("POSTGRES_PORT", "5432")
    
    if not os.path.exists(sql_file):
        print(f"[-] Error: SQL file '{sql_file}' not found.")
        return

    print(f"[*] Starting import of '{sql_file}' into database '{db_name}'...")
    
    # Set PGPASSWORD environment variable for psql
    os.environ["PGPASSWORD"] = db_pass
    
    try:
        # Step 1: Optional - Reset/Clear current DB (You can skip this if your SQL has DROP commands)
        # But for safety, we just run the import
        
        command = [
            "psql",
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-d", db_name,
            "-f", sql_file
        ]
        
        subprocess.run(command, check=True)
        print(f"[+] Import successful! Your server database is now up-to-date with local data.")
        
    except subprocess.CalledProcessError as e:
        print(f"[-] Import failed: {e}")
    except FileNotFoundError:
        print("[-] Error: 'psql' command not found. Please ensure PostgreSQL client tools are installed on the server.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Try to find the latest sql file in current dir if not provided
        sql_files = [f for f in os.listdir('.') if f.endswith('.sql')]
        if sql_files:
            sql_files.sort(reverse=True) # Get the most recent one
            target_file = sql_files[0]
            print(f"[*] No file specified, using most recent: {target_file}")
            import_database(target_file)
        else:
            print("[-] Usage: python scripts/db_import.py <your_backup_file.sql>")
    else:
        import_database(sys.argv[1])

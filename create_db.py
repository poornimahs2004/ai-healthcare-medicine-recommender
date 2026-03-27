import mysql.connector
import os
from dotenv import load_dotenv

# Load password from .env
load_dotenv()

print("--- Creating Database ---")

try:
    # Connect to MySQL Server (NOT the specific DB yet)
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "")
    )
    
    cursor = conn.cursor()
    
    # The Magic Command
    cursor.execute("CREATE DATABASE IF NOT EXISTS careai_db")
    
    print("✅ SUCCESS: Database 'careai_db' created successfully!")
    
    cursor.close()
    conn.close()

except mysql.connector.Error as err:
    print(f"❌ Failed: {err}")
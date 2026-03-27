import os
import mysql.connector
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

print("--- Testing MySQL Connection ---")
print(f"Host: {os.environ.get('DB_HOST', 'localhost')}")
print(f"User: {os.environ.get('DB_USER', 'root')}")
print(f"Database: {os.environ.get('DB_NAME', 'careai_db')}")

try:
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "careai_db")
    )
    
    if conn.is_connected():
        print("\n✅ SUCCESS: Connected to MySQL database!")
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        print("Tables in database:")
        for x in cursor:
            print(f" - {x[0]}")
        conn.close()
    else:
        print("\n❌ Connection failed (No specific error returned).")

except mysql.connector.Error as err:
    print(f"\n❌ CONNECTION FAILED: {err}")
    print("Hint: Check your password in backend/.env and ensure XAMPP/MySQL is running.")
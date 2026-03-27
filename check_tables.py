import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

try:
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database="careai_db"
    )
    
    if conn.is_connected():
        print("\n✅ CONNECTED to 'careai_db'")
        cursor = conn.cursor()
        
        # Check Tables
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        
        if not tables:
            print("⚠️  Database is empty (No tables found).")
            print("   -> Run 'python backend/app.py' once to create them.")
        else:
            print(f"📊 Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table[0]}")
                
                # Optional: Show columns to be 100% sure
                cursor.execute(f"DESCRIBE {table[0]}")
                columns = [col[0] for col in cursor.fetchall()]
                print(f"     Columns: {columns}")

        cursor.close()
        conn.close()

except mysql.connector.Error as err:
    print(f"\n❌ Error: {err}")
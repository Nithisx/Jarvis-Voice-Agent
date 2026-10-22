
import psycopg2

DATABASE_URL = "postgresql://postgres:123456@localhost:5432/voiceagent"

try:
    conn = psycopg2.connect(DATABASE_URL)
    print("Database connected successfully!")

    cursor = conn.cursor()
    cursor.execute("SELECT current_database(), current_user;")
    print("Database details:", cursor.fetchone())

    cursor.close()
    conn.close()

except Exception as e:
    print("Database connection failed:", e)

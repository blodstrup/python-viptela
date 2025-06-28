import psycopg2
from psycopg2 import OperationalError

def test_connection():
    # ✏️  Fill in your actual credentials here:
    conn_params = {
        "host":     "localhost",
        "port":     5432,
        "dbname":   "vmanage01",
        "user":     "postgres",
        "password": "8ds0jq"
    }

    try:
        # establish the connection
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()

        # run a simple check
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"✅ Connected successfully! Database version:\n   {version}")

    except OperationalError as e:
        print(f"❌ Could not connect to database:\n   {e}")

    finally:
        # cleanup
        if 'cur' in locals():  cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    test_connection()


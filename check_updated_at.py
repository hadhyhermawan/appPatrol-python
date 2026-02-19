from sqlalchemy import create_engine, text
import os
from datetime import datetime
import urllib.parse

# Database setup
# Password: Plnktbk3l@7654321
# We must encode the @ symbol as %40
password = urllib.parse.quote_plus("Plnktbk3l@7654321")
DATABASE_URL = f"mysql+pymysql://patrol:{password}@127.0.0.1:3306/patrol"

engine = create_engine(DATABASE_URL)

def check_user_updated_at():
    nik = "1801042008930003"
    print(f"Checking user with NIK: {nik}")
    
    with engine.connect() as connection:
        # Find user ID from NIK via users_karyawan
        query = text("""
            SELECT u.id, u.username, u.updated_at
            FROM users u
            JOIN users_karyawan uk ON u.id = uk.id_user
            WHERE uk.nik = :nik
        """)
        
        result = connection.execute(query, {"nik": nik}).fetchone()
        
        if result:
            print(f"User Found: ID={result[0]}, Username={result[1]}")
            print(f"Updated At (DB): {result[2]}")
            print(f"Current UTC Time: {datetime.utcnow()}")
        else:
            print("User not found linked to this NIK.")

if __name__ == "__main__":
    check_user_updated_at()

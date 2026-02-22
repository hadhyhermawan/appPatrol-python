import sys
import os

from sqlalchemy import text
from app.database import SessionLocal

def migrate():
    db = SessionLocal()
    try:
        db.execute(text("ALTER TABLE violations ADD COLUMN is_read TINYINT(1) DEFAULT 0;"))
        db.commit()
        print("Successfully added is_read column to violations table.")
    except Exception as e:
        print(f"Error (maybe already exists?): {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

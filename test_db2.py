import sys
import os
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    sql = """
        SELECT count(*) FROM user_agreements
    """
    results = db.execute(text(sql)).scalar()
    print(f"Total count: {results}")

    sql = """
        SELECT * FROM user_agreements LIMIT 5
    """
    results = db.execute(text(sql)).fetchall()
    print(results)
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()

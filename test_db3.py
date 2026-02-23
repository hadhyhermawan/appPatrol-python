import sys
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
results = db.execute(text("SELECT * FROM users WHERE id IN (252, 73)")).fetchall()
print("USERS:", results)
db.close()

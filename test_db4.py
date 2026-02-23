import sys
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
results = db.execute(text("SELECT u.name, u.username, u.email FROM users u WHERE id IN (252, 73)")).fetchall()
print("USERS:", results)
db.close()

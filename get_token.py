import sys
from app.database import SessionLocal
from sqlalchemy import text
from app.core.security import create_access_token

db = SessionLocal()
# get any valid user id
results = db.execute(text("SELECT id FROM users LIMIT 1")).scalar()
if results:
    token = create_access_token(data={"sub": str(results)})
    print(token)
db.close()

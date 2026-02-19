from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    print("--- ROLES ---")
    roles = db.execute(text("SELECT id, name, guard_name FROM roles")).fetchall()
    for r in roles:
        print(r)

    print("\n--- USERS (Sample) ---")
    users = db.execute(text("SELECT id, username, email FROM users LIMIT 5")).fetchall()
    for u in users:
        print(u)

    print("\n--- CHECK SPECIFIC USER '1801042008930002' ---")
    u = db.execute(text("SELECT id, username FROM users WHERE username = '1801042008930002'")).fetchone()
    if u:
        print(f"User Found: {u}")
        uid = u[0]
        roles = db.execute(text(f"SELECT * FROM model_has_roles WHERE model_id = {uid}")).fetchall()
        print(f"Roles: {roles}")
    else:
        print("User '1801042008930002' NOT FOUND")

except Exception as e:
    print(e)
finally:
    db.close()

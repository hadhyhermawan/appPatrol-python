import sys
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Assign role_id = 3 ('karyawan')
user_ids = [252, 253]
model_type = 'App\\Models\\User'

try:
    for u_id in user_ids:
        # Check if already exists
        check = db.execute(text("SELECT * FROM model_has_roles WHERE role_id = 3 AND model_id = :model_id AND model_type = :model_type"), {"model_id": u_id, "model_type": model_type}).fetchone()
        
        if not check:
            # Insert the role mapping
            db.execute(text("INSERT INTO model_has_roles (role_id, model_type, model_id) VALUES (3, :model_type, :model_id)"), {"model_type": model_type, "model_id": u_id})
            print(f"Assigned 'karyawan' role to user ID {u_id}")
        else:
            print(f"User ID {u_id} already has 'karyawan' role.")
            
    db.commit()
    print("Role update successful.")
except Exception as e:
    db.rollback()
    print(f"Error: {e}")

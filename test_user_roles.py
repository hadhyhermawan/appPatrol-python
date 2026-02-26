import sys
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Users, ModelHasRoles, Roles
from sqlalchemy import text

db = SessionLocal()

niks = ['1810022001990005', '1801032008930004']

for nik in niks:
    print(f"\nChecking NIK: {nik}")
    user = db.query(Users).filter(Users.username == nik).first()
    if user:
        print(f"User ID: {user.id}")
        # Get roles for this user
        roles = db.query(Roles).join(ModelHasRoles, Roles.id == ModelHasRoles.role_id).filter(ModelHasRoles.model_id == user.id).all()
        print(f"Roles:")
        for role in roles:
            print(f"- {role.name} (id: {role.id})")
            
        print("\nChecking users_karyawan pivot table:")
        pivot = db.execute(text("SELECT id_user, nik FROM users_karyawan WHERE nik = :nik OR id_user = :user_id"), 
                           {"nik": nik, "user_id": user.id}).fetchall()
        for p in pivot:
            print(f"- id_user: {p.id_user}, nik: {p.nik}")
    else:
        print("User not found in users table.")

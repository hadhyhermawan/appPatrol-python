import sys
import requests
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Users, Karyawan
from sqlalchemy import text
from app.routers.auth_legacy import create_android_token
from datetime import datetime

db = SessionLocal()
nik = '1801042008930002'

pivot = db.execute(text("SELECT id_user FROM users_karyawan WHERE nik = :nik"), {"nik": nik}).fetchone()
if not pivot:
    user = db.query(Users).filter(Users.username == nik).first()
    user_id = user.id
else:
    user_id = pivot[0]

user = db.query(Users).filter(Users.id == user_id).first()
token = create_android_token(data={'sub': str(user.id), 'username': user.username})

url = "http://localhost:8000/api/android/jamkerja/bulanan?month=2&year=2026"
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(url, headers=headers)

import json
print(json.dumps(resp.json(), indent=2))

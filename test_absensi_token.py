import sys
import pytz
from datetime import datetime, timedelta
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Karyawan, PengaturanUmum, PresensiJamkerja, Presensi, Users
from sqlalchemy import text
db = SessionLocal()
now = datetime.now(pytz.timezone('Asia/Jakarta'))
nik = '1801032008930004'

karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
if not karyawan:
    print("Karyawan not found")
    sys.exit()

pivot = db.execute(text("SELECT id_user FROM users_karyawan WHERE nik = :nik"), {"nik": nik}).fetchone()
if not pivot:
    print("User pivot not found")
    sys.exit()
    
user_id = pivot[0]
print(f"User ID from pivot is {user_id}")

user = db.query(Users).filter(Users.id == user_id).first()
if not user:
    print("User not found!")
    sys.exit()

import json
import base64

from app.core._legacy_sanctum import validate_sanctum_token
# we can just get a personal access token for testing
pat = db.execute(text("SELECT id, tokenable_id, token, name FROM personal_access_tokens WHERE tokenable_id = :uid LIMIT 1"), {"uid": user_id}).fetchone()

if pat:
    print(f"Found PAT token ID={pat[0]} for User={pat[1]} Name={pat[3]}")
    # Sanctum Tokens are usually sent as "id|token_hash_or_plaintext"
    print(f"Try to use: {pat[0]}|YOUR_PLAIN_TEXT_TOKEN_HERE (or we mock the test without full API call)")


import sys
sys.path.append('/var/www/appPatrol-python')
from app.database import SessionLocal
from app.models.models import Karyawan, Presensi
db = SessionLocal()
k = db.query(Karyawan).filter(Karyawan.nik == '1801032008930004').first()
if k:
    print(f'Nik: {k.nik} LockJamKerja: {k.lock_jam_kerja} Status:{k.status}')
else:
    print('Not found')
p = db.query(Presensi).filter(Presensi.nik == '1801032008930004').order_by(Presensi.tanggal.desc()).limit(3).all()
for x in p:
    print(f'Presensi: {x.tanggal} In:{x.jam_in} Out:{x.jam_out} Shift:{x.kode_jam_kerja}')

from app.database import SessionLocal
import datetime
from sqlalchemy import text
from app.models.models import Karyawan, Presensi, Violation

db = SessionLocal()
kemarin = datetime.date.today() - datetime.timedelta(days=1)

active = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1').all()
pres = db.query(Presensi.nik).filter(Presensi.tanggal == kemarin).all()
nik_pres = {p[0] for p in pres}

ambigu = [k for k in active if k.nik not in nik_pres]

inserted = 0
for k in ambigu:
    exists = db.query(Violation).filter(Violation.nik == k.nik, Violation.tanggal_pelanggaran == kemarin, Violation.violation_type == 'ABSENT').count()
    if exists == 0:
        new_v = Violation(
            nik=k.nik, 
            tanggal_pelanggaran=kemarin, 
            jenis_pelanggaran="SEDANG", 
            keterangan="Tidak ada data presensi (Alpha)", 
            status="OPEN", 
            source="SYSTEM", 
            violation_type="ABSENT", 
            sanksi=""
        )
        db.add(new_v)
        inserted += 1

db.commit()
print(f"Suksess Insert {inserted} violations Alpha KEMARIN")

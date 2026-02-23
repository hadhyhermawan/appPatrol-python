from app.database import SessionLocal
import datetime
from sqlalchemy import text
from app.models.models import Karyawan, Presensi, Violation

db = SessionLocal()

def fix_past_days(days_back=7):
    print(f"Memulai sinkronisasi data {days_back} hari ke belakang...")
    today = datetime.date.today()
    inserted_total = 0
    
    # Pre-fetch all active employees
    active_karyawan = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1').all()
    print(f"Total karyawan aktif: {len(active_karyawan)}")

    for i in range(1, days_back + 1):
        target_date = today - datetime.timedelta(days=i)
        print(f"\nMemproses tanggal: {target_date}")
        
        # 1. Fetch presensi for this date
        pres_for_date = db.query(Presensi.nik).filter(Presensi.tanggal == target_date).all()
        nik_pres_date = {p[0] for p in pres_for_date}
        
        # 2. Identify alphas (active but no presensi)
        ambigu_karyawan = [k for k in active_karyawan if k.nik not in nik_pres_date]
        print(f"Karyawan Alpha (Kosong Absen): {len(ambigu_karyawan)}")
        
        inserted_for_date = 0
        for k in ambigu_karyawan:
            # Check if violation already exists to avoid duplicates
            exists = db.query(Violation).filter(
                Violation.nik == k.nik, 
                Violation.tanggal_pelanggaran == target_date, 
                Violation.violation_type == 'ABSENT'
            ).count()
            
            if exists == 0:
                new_v = Violation(
                    nik=k.nik, 
                    tanggal_pelanggaran=target_date, 
                    jenis_pelanggaran="SEDANG", 
                    keterangan="Tidak ada data presensi / Tidak absen (Alpha) - Hasil Sinkronisasi Mundur", 
                    status="OPEN", 
                    source="SYSTEM", 
                    violation_type="ABSENT", 
                    sanksi=""
                )
                db.add(new_v)
                inserted_for_date += 1
                inserted_total += 1
                
        db.commit()
        print(f"Berhasil menambahkan {inserted_for_date} tiket Alpha untuk tanggal {target_date}")

    print(f"\nSINKRONISASI SELESAI! Total tiket pelanggaran Alpha masa lalu yang berhasil ditambahkan: {inserted_total}")

# Run for the past 7 days (1 minggu ke belakang)
fix_past_days(7)


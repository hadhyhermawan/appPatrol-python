from app.database import SessionLocal
from app.models.models import SetJamKerjaByDate, PresensiJamkerja
from sqlalchemy import text
from datetime import date

db = SessionLocal()
tgl = date(2026, 2, 19)

print(f"Checking assignments for {tgl}...")

try:
    # 1. Get assignments
    by_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.tanggal == tgl).all()
    print(f"ByDate Count: {len(by_date)}")
    codes_list = [x.kode_jam_kerja for x in by_date]
    codes = set(codes_list)
    print(f"Codes found ({len(codes)}): {codes}")

    # 2. Check PresensiJamkerja
    if codes:
        jks = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja.in_(codes)).all()
        print(f"Found {len(jks)} matching JamKerja definitions.")
        for jk in jks:
            print(f" - [{jk.kode_jam_kerja}] {jk.nama_jam_kerja} | In: {jk.jam_masuk} | Out: {jk.jam_pulang}")
    else:
        print("No assignments found in SetJamKerjaByDate.")

    # 3. Check Dept Detail days
    print("\nChecking Dept Detail unique days:")
    rows = db.execute(text("SELECT DISTINCT hari FROM presensi_jamkerja_bydept_detail")).fetchall()
    print([r[0] for r in rows if r])

except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()

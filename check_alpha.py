import pymysql

db = pymysql.connect(host="localhost",user="k3guard2",password="2x341!@#R2x341!@#R",database="k3guard2")
c = db.cursor()

from datetime import date, timedelta
today = date.today()
yesterday = today - timedelta(days=1)

print(f"--- Data untuk Tanggal HARI INI: {today} ---")
c.execute("SELECT COUNT(*) FROM karyawan WHERE status_aktif_karyawan='1'")
active = c.fetchone()[0]
print(f"Total Karyawan Aktif: {active}")

c.execute("SELECT COUNT(*) FROM presensi WHERE tanggal=%s AND status='A'", (today,))
explicit_a = c.fetchone()[0]
print(f"Karyawan di database eksplisit Alpha (Status 'A'): {explicit_a}")

c.execute("SELECT COUNT(DISTINCT nik) FROM presensi WHERE tanggal=%s", (today,))
absen_today = c.fetchone()[0]
implicit_a = active - absen_today
print(f"Karyawan Alpha karena Kosong Absen (Tidak ada data presensi): {implicit_a}")
print(f"TOTAL GABUNGAN ALPHA HARI INI: {explicit_a + implicit_a}")
print("")

print(f"--- Data untuk Tanggal KEMARIN: {yesterday} ---")
c.execute("SELECT COUNT(*) FROM presensi WHERE tanggal=%s AND status='A'", (yesterday,))
explicit_a_y = c.fetchone()[0]
print(f"Karyawan di database eksplisit Alpha (Status 'A'): {explicit_a_y}")

c.execute("SELECT COUNT(DISTINCT nik) FROM presensi WHERE tanggal=%s", (yesterday,))
absen_yesterday = c.fetchone()[0]
implicit_a_y = active - absen_yesterday
print(f"Karyawan Alpha karena Kosong Absen (Tidak ada data presensi): {implicit_a_y}")
print(f"TOTAL GABUNGAN ALPHA KEMARIN: {explicit_a_y + implicit_a_y}")
db.close()

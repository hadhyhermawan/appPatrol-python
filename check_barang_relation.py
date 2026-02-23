from app.database import SessionLocal
from app.models.models import Barang, BarangMasuk, BarangKeluar
db = SessionLocal()
b = db.query(Barang).order_by(Barang.id_barang.desc()).limit(10).all()
for i in b:
    print(f"ID {i.id_barang}")
    if i.barang_masuk:
        print("  Masuk:", i.barang_masuk[0].karyawan.nama_karyawan if i.barang_masuk[0].karyawan else 'None')
    if i.barang_keluar:
        print("  Keluar:", i.barang_keluar[0].karyawan.nama_karyawan if i.barang_keluar[0].karyawan else 'None')

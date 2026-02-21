from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, case, desc, and_, or_, text
from datetime import datetime, timedelta, date, time
import pytz
from typing import Optional, List, Dict, Any

from app.database import get_db
from app.models.models import (
    Users, Karyawan, Departemen, Cabang, Jabatan,
    Presensi, PresensiJamkerja
)
from app.routers.auth import get_current_user
from app.routers.auth_legacy import get_current_user_nik

router = APIRouter(
    prefix="/api/android",
    tags=["Beranda Legacy (Android)"],
    responses={404: {"description": "Not found"}},
)

# Timezone WIB
WIB = pytz.timezone('Asia/Jakarta')

BASE_STORAGE_URL = "https://frontend.k3guard.com/api-py/storage/"

def get_image_url(path: str):
    if not path:
        return None
    if path.startswith("http"):
        return path
    return f"{BASE_STORAGE_URL}karyawan/{path}"

@router.get("/beranda")
async def get_beranda(
    db: Session = Depends(get_db),
    nik: str = Depends(get_current_user_nik)
):
    try:
        # 1. Get User Karyawan Data
        # Join Karyawan, Jabatan, Dept, Cabang
        karyawan_data = db.query(
            Karyawan, 
            Jabatan.nama_jabatan, 
            Departemen.nama_dept, 
            Cabang.nama_cabang, 
            Cabang.kode_cabang
        ).join(
            Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan
        ).join(
            Departemen, Karyawan.kode_dept == Departemen.kode_dept
        ).join(
            Cabang, Karyawan.kode_cabang == Cabang.kode_cabang
        ).filter(
            Karyawan.nik == nik
        ).first()

        if not karyawan_data:
             return {
                "status": False,
                "message": "Data karyawan tidak ditemukan"
            }
        
        karyawan, nama_jabatan, nama_dept, nama_cabang, kode_cabang = karyawan_data

        # 2. Masa Aktif Kartu
        sisa_hari = None
        if karyawan.masa_aktif_kartu_anggota:
            today = datetime.now(WIB).date()
            # Convert masa_aktif to date if it's not already
            if isinstance(karyawan.masa_aktif_kartu_anggota, str):
                try:
                    masa_aktif = datetime.strptime(karyawan.masa_aktif_kartu_anggota, "%Y-%m-%d").date()
                except ValueError:
                    masa_aktif = None
            else:
                masa_aktif = karyawan.masa_aktif_kartu_anggota
            
            if masa_aktif:
                # Diff in days (target - today)
                delta = masa_aktif - today
                sisa_hari = delta.days
        
        # Foto URL
        foto_url = get_image_url(karyawan.foto) if karyawan.foto else None

        # 3. Presensi Logic (Besok -> Hari Ini -> Kemarin Lintas Hari)
        hari_ini_str = datetime.now(WIB).strftime("%Y-%m-%d")
        besok_str = (datetime.now(WIB) + timedelta(days=1)).strftime("%Y-%m-%d")
        kemarin_str = (datetime.now(WIB) - timedelta(days=1)).strftime("%Y-%m-%d")

        presensi_hari_ini = None

        # A. Cek Besok
        presensi_hari_ini = db.query(Presensi).filter(
            Presensi.nik == karyawan.nik,
            Presensi.tanggal == besok_str
        ).order_by(desc(Presensi.id)).first()

        # B. Cek Hari Ini
        if not presensi_hari_ini:
            presensi_hari_ini = db.query(Presensi).filter(
                Presensi.nik == karyawan.nik,
                Presensi.tanggal == hari_ini_str
            ).order_by(desc(Presensi.id)).first()
        
        # C. Cek Kemarin (Lintas Hari & Belum Pulang)
        if not presensi_hari_ini:
            presensi_hari_ini = db.query(Presensi).filter(
                Presensi.nik == karyawan.nik,
                Presensi.tanggal == kemarin_str,
                Presensi.lintashari == 1,
                Presensi.jam_out == None
            ).order_by(desc(Presensi.id)).first()

        # 4. Data Presensi (Riwayat 30 Terakhir — hanya field yang dipakai Android)
        riwayat_query = db.query(
            Presensi.tanggal,
            Presensi.jam_in,
            Presensi.jam_out,
            Presensi.foto_in,
            Presensi.foto_out,
            Presensi.kode_jam_kerja,
            PresensiJamkerja.nama_jam_kerja,
            PresensiJamkerja.jam_masuk,
            PresensiJamkerja.jam_pulang,
            PresensiJamkerja.lintashari
        ).join(
            PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja
        ).filter(
            Presensi.nik == karyawan.nik
        ).order_by(
            desc(Presensi.tanggal)
        ).limit(30).all()

        def fmt_time(v):
            if isinstance(v, datetime): return v.strftime("%H:%M:%S")
            if isinstance(v, (date, time)): return str(v)
            return v

        datapresensi = [
            {
                "tanggal": str(row.tanggal) if row.tanggal else None,
                "jam_in": fmt_time(row.jam_in),
                "jam_out": fmt_time(row.jam_out),
                "foto_in": row.foto_in,
                "foto_out": row.foto_out,
                "kode_jam_kerja": row.kode_jam_kerja,
                "nama_jam_kerja": row.nama_jam_kerja,
                "jam_masuk": str(row.jam_masuk) if row.jam_masuk else None,
                "jam_pulang": str(row.jam_pulang) if row.jam_pulang else None,
                "lintashari": row.lintashari
            }
            for row in riwayat_query
        ]

        # Serialize presensi_hari_ini — hanya field yang dipakai Android
        presensi_hari_ini_dict = None
        if presensi_hari_ini:
            jam_kerja = db.query(PresensiJamkerja).filter(
                PresensiJamkerja.kode_jam_kerja == presensi_hari_ini.kode_jam_kerja
            ).first()
            presensi_hari_ini_dict = {
                "tanggal": str(presensi_hari_ini.tanggal) if presensi_hari_ini.tanggal else None,
                "jam_in": fmt_time(presensi_hari_ini.jam_in),
                "jam_out": fmt_time(presensi_hari_ini.jam_out),
                "foto_in": presensi_hari_ini.foto_in,
                "foto_out": presensi_hari_ini.foto_out,
                "kode_jam_kerja": presensi_hari_ini.kode_jam_kerja,
                "nama_jam_kerja": jam_kerja.nama_jam_kerja if jam_kerja else None,
                "jam_masuk": str(jam_kerja.jam_masuk) if jam_kerja and jam_kerja.jam_masuk else None,
                "jam_pulang": str(jam_kerja.jam_pulang) if jam_kerja and jam_kerja.jam_pulang else None,
                "lintashari": jam_kerja.lintashari if jam_kerja else None
            }

        return {
            "status": True,
            "data": {
                "karyawan": {
                    "nik": karyawan.nik,
                    "nama_karyawan": karyawan.nama_karyawan,
                    "kode_dept": karyawan.kode_dept,
                    "kode_cabang": kode_cabang,
                    "nama_jabatan": nama_jabatan,
                    "nama_dept": nama_dept,
                    "nama_cabang": nama_cabang,
                    "foto": foto_url,
                    "kode_jadwal": karyawan.kode_jadwal,
                    "sisa_hari_masa_aktif_kartu": sisa_hari
                },
                "presensi_hari_ini": presensi_hari_ini_dict,
                "datapresensi": datapresensi
            }
        }

    except Exception as e:
        print(f"Error Beranda Legacy: {e}")
        return {
            "status": False,
            "message": "Terjadi kesalahan server",
            "detail": str(e)
        }

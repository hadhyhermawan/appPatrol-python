from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, case, desc, and_, or_, text
from datetime import datetime, timedelta, date, time
import pytz
from typing import Optional, List, Dict, Any

from app.database import get_db
from app.models.models import (
    Users, Karyawan, Departemen, Cabang, Jabatan,
    Presensi, PresensiJamkerja, Lembur,
    PresensiIzinabsenApprove, PresensiIzinabsen,
    PresensiIzinsakitApprove, PresensiIzinsakit,
    PresensiIzincutiApprove, PresensiIzincuti
)
from app.routers.auth import get_current_user
# Use get_current_user_nik from auth_legacy if utilizing legacy token mechanism, 
# or use get_current_user if switching to standard auth.
# Assuming we want to support the existing Android Auth (Sanctum/Legacy Token).
from app.routers.auth_legacy import get_current_user_nik 

router = APIRouter(
    prefix="/api/android",
    tags=["Beranda Legacy (Android)"],
    responses={404: {"description": "Not found"}},
)

# Timezone WIB
WIB = pytz.timezone('Asia/Jakarta')

def get_image_url(request, path: str):
    if not path:
        return None
    # Hardcoded base URL for storage
    base_url = "https://k3guard.com/storage" 
    # Laravel logic: asset('storage/karyawan/' . $karyawan->foto)
    # Check if path already contains full url (rare)
    if path.startswith("http"):
        return path
    return f"{base_url}/karyawan/{path}"

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
        foto_url = get_image_url(None, karyawan.foto) if karyawan.foto else None

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

        # 4. Data Presensi (Riwayat 30 Terakhir + Detail)
        riwayat_query = db.query(
            Presensi,
            PresensiJamkerja.nama_jam_kerja,
            PresensiJamkerja.jam_masuk,
            PresensiJamkerja.jam_pulang,
            PresensiJamkerja.total_jam,
            PresensiJamkerja.lintashari,
            PresensiIzinabsen.keterangan.label("keterangan_izin"),
            PresensiIzinsakit.keterangan.label("keterangan_izin_sakit"),
            PresensiIzincuti.keterangan.label("keterangan_izin_cuti")
        ).join(
            PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja
        ).outerjoin(
            PresensiIzinabsenApprove, Presensi.id == PresensiIzinabsenApprove.id_presensi
        ).outerjoin(
            PresensiIzinabsen, PresensiIzinabsenApprove.kode_izin == PresensiIzinabsen.kode_izin
        ).outerjoin(
            PresensiIzinsakitApprove, Presensi.id == PresensiIzinsakitApprove.id_presensi
        ).outerjoin(
            PresensiIzinsakit, PresensiIzinsakitApprove.kode_izin_sakit == PresensiIzinsakit.kode_izin_sakit
        ).outerjoin(
            PresensiIzincutiApprove, Presensi.id == PresensiIzincutiApprove.id_presensi
        ).outerjoin(
            PresensiIzincuti, PresensiIzincutiApprove.kode_izin_cuti == PresensiIzincuti.kode_izin_cuti
        ).filter(
            Presensi.nik == karyawan.nik
        ).order_by(
            desc(Presensi.tanggal)
        ).limit(30).all()

        datapresensi = []
        for row in riwayat_query:
            p, nama_jk, jam_m, jam_p, tot_jam, lh, ket_izin, ket_sakit, ket_cuti = row
            
            p_dict = {c.name: getattr(p, c.name) for c in p.__table__.columns}
            
            # Format standard dates to string with specific handling for time fields
            for k, v in p_dict.items():
                if k in ['jam_in', 'jam_out', 'istirahat_in', 'istirahat_out'] and isinstance(v, datetime):
                    p_dict[k] = v.strftime("%H:%M:%S")
                elif isinstance(v, (date, datetime, time)):
                    p_dict[k] = str(v)

            p_dict.update({
                "nama_jam_kerja": nama_jk,
                "jam_masuk": str(jam_m) if jam_m else None,
                "jam_pulang": str(jam_p) if jam_p else None,
                "total_jam": tot_jam,
                "lintashari": lh,
                "keterangan_izin": ket_izin,
                "keterangan_izin_sakit": ket_sakit,
                "keterangan_izin_cuti": ket_cuti
            })
            datapresensi.append(p_dict)

        # 5. Rekap Presensi Bulan Ini
        current_month = datetime.now(WIB).month
        current_year = datetime.now(WIB).year
        
        rekap = db.query(
            func.sum(case((Presensi.status == 'h', 1), else_=0)).label('hadir'),
            func.sum(case((Presensi.status == 'i', 1), else_=0)).label('izin'),
            func.sum(case((Presensi.status == 's', 1), else_=0)).label('sakit'),
            func.sum(case((Presensi.status == 'a', 1), else_=0)).label('alpa'),
            func.sum(case((Presensi.status == 'c', 1), else_=0)).label('cuti')
        ).filter(
            Presensi.nik == karyawan.nik,
            func.extract('month', Presensi.tanggal) == current_month,
            func.extract('year', Presensi.tanggal) == current_year
        ).first()

        rekappresensi = {
            "hadir": int(rekap.hadir or 0),
            "izin": int(rekap.izin or 0),
            "sakit": int(rekap.sakit or 0),
            "alpa": int(rekap.alpa or 0),
            "cuti": int(rekap.cuti or 0)
        }

        # 6. Lembur
        lembur_query = db.query(Lembur).filter(
            Lembur.nik == karyawan.nik,
            Lembur.status == '1'
        ).order_by(desc(Lembur.id)).limit(10).all()
        
        lembur_data = []
        for l in lembur_query:
            l_dict = {c.name: getattr(l, c.name) for c in Lembur.__table__.columns}
            for k, v in l_dict.items():
                if isinstance(v, (date, datetime, time)):
                    l_dict[k] = str(v)
            lembur_data.append(l_dict)

        notiflembur = db.query(Lembur).filter(
            Lembur.nik == karyawan.nik,
            Lembur.status == '1',
            or_(Lembur.lembur_in == None, Lembur.lembur_out == None)
        ).count()

        # Serialize presensi_hari_ini manually if exists
        presensi_hari_ini_dict = None
        if presensi_hari_ini:
            # Convert SQLAlchemy object to dict
            p_dict = {c.name: getattr(presensi_hari_ini, c.name) for c in presensi_hari_ini.__table__.columns}
            
            # Format time fields
            for k, v in p_dict.items():
                if k in ['jam_in', 'jam_out', 'istirahat_in', 'istirahat_out'] and isinstance(v, datetime):
                    p_dict[k] = v.strftime("%H:%M:%S")
                elif isinstance(v, (date, datetime, time)):
                    p_dict[k] = str(v)
            
            presensi_hari_ini_dict = p_dict

        # Construct Final Response Structure
        # Android expects: { status: true, data: { ... } }
        
        return {
            "status": True,
            "data": {
                "karyawan": {
                    "nik": karyawan.nik,
                    "nama_karyawan": karyawan.nama_karyawan,
                    "kode_dept": karyawan.kode_dept,
                    "nama_jabatan": nama_jabatan,
                    "nama_dept": nama_dept,
                    "nama_cabang": nama_cabang,
                    "kode_cabang": kode_cabang,
                    "foto": foto_url,
                    "sisa_hari_masa_aktif_kartu": sisa_hari
                },
                "presensi_hari_ini": presensi_hari_ini_dict,
                "datapresensi": datapresensi,
                "rekappresensi": rekappresensi,
                "lembur": lembur_data,
                "notiflembur": notiflembur
            }
        }

    except Exception as e:
        print(f"Error Beranda Legacy: {e}")
        return {
            "status": False,
            "message": "Terjadi kesalahan server",
            "detail": str(e)
        }

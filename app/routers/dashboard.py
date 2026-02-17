from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case, and_, or_
from app.database import get_db
from app.models.models import Presensi, Karyawan, Cabang, PatrolSessions, Departemen
from datetime import date, timedelta, datetime

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
    responses={404: {"description": "Not found"}},
)

@router.get("")
async def get_dashboard_stats(
    tanggal: str = None,
    kode_cabang: str = None,
    kode_dept: str = None,
    db: Session = Depends(get_db)
):
    """Get dashboard statistics"""
    target_date = datetime.strptime(tanggal, '%Y-%m-%d').date() if tanggal else date.today()
    
    # Rekap Presensi
    rekap_query = db.query(
        func.sum(case((Presensi.status == 'h', 1), else_=0)).label('hadir'),
        func.sum(case((Presensi.status == 'i', 1), else_=0)).label('izin'),
        func.sum(case((Presensi.status == 's', 1), else_=0)).label('sakit'),
        func.sum(case((Presensi.status == 'c', 1), else_=0)).label('cuti'),
        func.sum(case((Presensi.status == 'a', 1), else_=0)).label('alfa')
    ).join(Karyawan, Presensi.nik == Karyawan.nik)\
     .filter(func.date(Presensi.tanggal) == target_date)
    
    if kode_cabang:
        rekap_query = rekap_query.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        rekap_query = rekap_query.filter(Karyawan.kode_dept == kode_dept)
    
    rekap = rekap_query.first()
    
    # Patroli Aktif
    patroli_aktif = db.query(PatrolSessions)\
        .join(Karyawan, PatrolSessions.nik == Karyawan.nik)\
        .filter(PatrolSessions.status == 'active')
    
    if kode_cabang:
        patroli_aktif = patroli_aktif.filter(Karyawan.kode_cabang == kode_cabang)
    
    patroli_aktif_count = patroli_aktif.count()
    
    # Presensi Terbuka
    presensi_open = db.query(Presensi)\
        .join(Karyawan, Presensi.nik == Karyawan.nik)\
        .filter(and_(Presensi.jam_in.isnot(None), Presensi.jam_out.is_(None)))
    
    if kode_cabang:
        presensi_open = presensi_open.filter(Karyawan.kode_cabang == kode_cabang)
    
    presensi_open_count = presensi_open.count()
    
    # Total Karyawan Aktif
    total_karyawan_query = db.query(func.count(Karyawan.nik))\
        .filter(Karyawan.status_aktif_karyawan == '1')
    
    if kode_cabang:
        total_karyawan_query = total_karyawan_query.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        total_karyawan_query = total_karyawan_query.filter(Karyawan.kode_dept == kode_dept)
    
    total_karyawan = total_karyawan_query.scalar()
    
    # Hitung perubahan dari kemarin
    yesterday = target_date - timedelta(days=1)
    rekap_yesterday = db.query(
        func.sum(case((Presensi.status == 'h', 1), else_=0)).label('hadir')
    ).join(Karyawan, Presensi.nik == Karyawan.nik)\
     .filter(func.date(Presensi.tanggal) == yesterday)
    
    if kode_cabang:
        rekap_yesterday = rekap_yesterday.filter(Karyawan.kode_cabang == kode_cabang)
    
    yesterday_hadir = rekap_yesterday.first().hadir or 0
    
    # Top Cabang Performance
    top_cabang = db.query(
        Cabang.kode_cabang,
        Cabang.nama_cabang,
        func.count(Karyawan.nik).label('total_karyawan')
    )\
        .outerjoin(Karyawan, and_(
            Karyawan.kode_cabang == Cabang.kode_cabang,
            Karyawan.status_aktif_karyawan == '1'
        ))\
        .group_by(Cabang.kode_cabang, Cabang.nama_cabang)\
        .order_by(desc('total_karyawan'))\
        .limit(5)\
        .all()
    
    # Patroli Aktif List
    patroli_list = db.query(
        PatrolSessions,
        Karyawan.nama_karyawan,
        Cabang.nama_cabang
    )\
        .join(Karyawan, PatrolSessions.nik == Karyawan.nik)\
        .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
        .filter(PatrolSessions.status == 'active')\
        .order_by(desc(PatrolSessions.jam_patrol))\
        .limit(5)\
        .all()
    
    # Presensi Open List
    open_list = db.query(
        Presensi,
        Karyawan.nama_karyawan,
        Karyawan.kode_dept,
        Cabang.nama_cabang
    )\
        .join(Karyawan, Presensi.nik == Karyawan.nik)\
        .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
        .filter(and_(Presensi.jam_in.isnot(None), Presensi.jam_out.is_(None)))\
        .order_by(desc(Presensi.jam_in))\
        .limit(5)\
        .all()
    
    # Tidak Hadir List
    tidak_hadir = db.query(
        Karyawan.nik,
        Karyawan.nama_karyawan,
        Karyawan.kode_dept,
        Cabang.nama_cabang,
        Presensi.status
    )\
        .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
        .outerjoin(Presensi, and_(
            Presensi.nik == Karyawan.nik,
            func.date(Presensi.tanggal) == target_date
        ))\
        .filter(
            Karyawan.status_aktif_karyawan == '1',
            or_(Presensi.jam_in.is_(None), Presensi.status.in_(['i', 's', 'c', 'a']))
        )\
        .limit(5)\
        .all()
    
    return {
        "stats": {
            "kehadiran": {
                "hadir": rekap.hadir or 0,
                "izin": rekap.izin or 0,
                "sakit": rekap.sakit or 0,
                "cuti": rekap.cuti or 0,
                "alfa": rekap.alfa or 0,
                "change": (rekap.hadir or 0) - yesterday_hadir,
                "changePercent": round(((rekap.hadir or 0) - yesterday_hadir) / max(yesterday_hadir, 1) * 100, 1) if yesterday_hadir > 0 else 0
            },
            "patroli_aktif": {
                "value": patroli_aktif_count,
                "change": 5,
                "changePercent": 7.9
            },
            "izin_sakit": {
                "value": (rekap.izin or 0) + (rekap.sakit or 0),
                "change": -2,
                "changePercent": -15.4
            },
            "total_karyawan": {
                "value": total_karyawan or 0,
                "change": 3,
                "changePercent": 1.9
            },
            "presensi_open": presensi_open_count,
            "tamu_hari_ini": 0,  # TODO: implement tamu count
            "barang_hari_ini": 0  # TODO: implement barang count
        },
        "top_cabang": [
            {
                "kode_cabang": c.kode_cabang,
                "nama_cabang": c.nama_cabang,
                "total_karyawan": c.total_karyawan,
                "trend": "up",
                "change": 2.5
            }
            for c in top_cabang
        ],
        "patroli_aktif_list": [
            {
                "nama_karyawan": p[1],
                "nama_cabang": p[2],
                "jam_patrol": p[0].jam_patrol.isoformat() if p[0].jam_patrol else None,
                "nik": p[0].nik
            }
            for p in patroli_list
        ],
        "presensi_open_list": [
            {
                "nama_karyawan": p[1],
                "kode_dept": p[2],
                "nama_cabang": p[3],
                "jam_in": p[0].jam_in.isoformat() if p[0].jam_in else None,
                "nik": p[0].nik
            }
            for p in open_list
        ],
        "tidak_hadir_list": [
            {
                "nik": t.nik,
                "nama_karyawan": t.nama_karyawan,
                "kode_dept": t.kode_dept,
                "nama_cabang": t.nama_cabang,
                "status": t.status or "a"
            }
            for t in tidak_hadir
        ],
        "tanggal": target_date.isoformat()
    }

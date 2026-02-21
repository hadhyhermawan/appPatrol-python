from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case, and_, or_
from app.database import get_db
from app.models.models import Presensi, Karyawan, Cabang, PatrolSessions, Departemen, Tamu, BarangMasuk, BarangKeluar, EmployeeLocations, EmployeeStatus
from datetime import date, timedelta, datetime
from app.core.permissions import get_current_user

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(get_current_user)],
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
        func.sum(case((Presensi.status == 'a', 1), else_=0)).label('alfa'),
        func.sum(case((Presensi.status == 'ta', 1), else_=0)).label('lupa_pulang'),  # ← baru
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
        .limit(5)\
        .all()
        
    # Tamu Hari Ini
    tamu_query = db.query(func.count(Tamu.id_tamu))\
        .filter(func.date(Tamu.jam_masuk) == target_date)
        
    # Barang Hari Ini (Masuk + Keluar)
    # Note: BarangMasuk & BarangKeluar are separate tables.
    barang_masuk_count = db.query(func.count(BarangMasuk.id_barang_masuk))\
        .filter(func.date(BarangMasuk.tgl_jam_masuk) == target_date).scalar() or 0
        
    barang_keluar_count = db.query(func.count(BarangKeluar.id_barang_keluar))\
        .filter(func.date(BarangKeluar.tgl_jam_keluar) == target_date).scalar() or 0
        
    barang_count = barang_masuk_count + barang_keluar_count
    
    if kode_cabang:
        tamu_query = tamu_query.join(Karyawan, Tamu.nik_satpam == Karyawan.nik)\
            .filter(Karyawan.kode_cabang == kode_cabang)
            
    tamu_count = tamu_query.scalar() or 0
    
    # 8. Chart Data: Monthly Performance Trend (Last 30 Days)
    # Group by Date, Count Presence (H, I, S, A)
    endDate = target_date
    startDate = endDate - timedelta(days=29)
    
    chart_query = db.query(
        func.date(Presensi.tanggal).label('date'),
        func.sum(case((Presensi.status == 'h', 1), else_=0)).label('hadir'),
        func.sum(case((Presensi.status.in_(['i', 's', 'c']), 1), else_=0)).label('tidak_hadir') # Izin/Sakit/Cuti
    ).join(Karyawan, Presensi.nik == Karyawan.nik)\
     .filter(func.date(Presensi.tanggal) >= startDate)\
     .filter(func.date(Presensi.tanggal) <= endDate)\
     .group_by(func.date(Presensi.tanggal))\
     .order_by(func.date(Presensi.tanggal))
     
    if kode_cabang:
        chart_query = chart_query.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        chart_query = chart_query.filter(Karyawan.kode_dept == kode_dept)
        
    chart_results = chart_query.all()
    
    # Format for ApexCharts (or similar)
    chart_data = {
        "categories": [],
        "series": [
            {"name": "Hadir", "data": []},
            {"name": "Izin/Sakit", "data": []}
        ]
    }
    
    # Fill missing dates with 0
    current_d = startDate
    result_map = {r.date: r for r in chart_results}
    
    while current_d <= endDate:
        d_str = current_d.strftime('%d %b')
        chart_data["categories"].append(d_str)
        
        if current_d in result_map:
            res = result_map[current_d]
            chart_data["series"][0]["data"].append(int(res.hadir or 0))
            chart_data["series"][1]["data"].append(int(res.tidak_hadir or 0))
        else:
            chart_data["series"][0]["data"].append(0)
            chart_data["series"][1]["data"].append(0)
            
        current_d += timedelta(days=1)

    # ... (existing code: Target Patroli)
    
    # Target Patroli (Active Schedules)
    from app.models.models import PatrolSchedules # Ensure import is available or use existing
    
    target_patroli_query = db.query(func.count(PatrolSchedules.id))\
        .filter(PatrolSchedules.is_active == 1)
        
    if kode_cabang:
        target_patroli_query = target_patroli_query.filter(PatrolSchedules.kode_cabang == kode_cabang)
    if kode_dept:
        target_patroli_query = target_patroli_query.filter(PatrolSchedules.kode_dept == kode_dept)
        
    target_patroli_count = target_patroli_query.scalar() or 0
    
    # 7. Recent Activities (Consolidated Feed)
    recent_activities = []
    
    # Fetch recent Presensi events (Last 10 updated)
    recent_presensi = db.query(Presensi, Karyawan.nama_karyawan)\
        .join(Karyawan, Presensi.nik == Karyawan.nik)\
        .filter(func.date(Presensi.tanggal) == target_date)\
        .order_by(desc(Presensi.updated_at))\
        .limit(10)\
        .all()
        
    for p, nama in recent_presensi:
        # Check In Event
        if p.jam_in:
            recent_activities.append({
                "type": "attendance",
                "name": nama,
                "action": "Absen Masuk",
                "timestamp": p.jam_in, # DateTime
                "icon": "UserCheck",
                "color": "blue"
            })
            
        # Check Out Event
        if p.jam_out:
            recent_activities.append({
                "type": "attendance",
                "name": nama,
                "action": "Absen Pulang",
                "timestamp": p.jam_out, # DateTime
                "icon": "Clock",
                "color": "purple"
            })
            
    # Fetch recent Patrol events
    recent_patrols = db.query(PatrolSessions, Karyawan.nama_karyawan)\
        .join(Karyawan, PatrolSessions.nik == Karyawan.nik)\
        .filter(PatrolSessions.tanggal == target_date)\
        .order_by(desc(PatrolSessions.updated_at))\
        .limit(10)\
        .all()
        
    for p, nama in recent_patrols:
        # Start Patrol
        if p.jam_patrol:
             # jam_patrol is Time, combine with date
             dt_start = datetime.combine(p.tanggal, p.jam_patrol)
             recent_activities.append({
                 "type": "patrol",
                 "name": nama,
                 "action": "Memulai Patroli",
                 "timestamp": dt_start,
                 "icon": "Shield",
                 "color": "green"
             })
        
        # Finish Patrol
        if p.status == 'complete':
            # Use updated_at as completion time proxy
             recent_activities.append({
                 "type": "patrol",
                 "name": nama,
                 "action": "Menyelesaikan Patroli",
                 "timestamp": p.updated_at,
                 "icon": "Shield",
                 "color": "green"
             })
             
    # Sort by timestamp desc and take top 10
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    final_activities = []
    
    for a in recent_activities[:10]:
        final_activities.append({
            "type": a['type'],
            "name": a['name'],
            "action": a['action'],
            "timestamp": a['timestamp'].isoformat() if a['timestamp'] else None,
            "icon": a['icon'],
            "color": a['color']
        })
    
    return {
        "stats": {
            "kehadiran": {
                "hadir": rekap.hadir or 0,
                "izin": rekap.izin or 0,
                "sakit": rekap.sakit or 0,
                "cuti": rekap.cuti or 0,
                "alfa": rekap.alfa or 0,
                "lupa_pulang": rekap.lupa_pulang or 0,  # ← status 'ta'
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
            "tamu_hari_ini": tamu_count,
            "barang_hari_ini": barang_count,
            "target_patroli": target_patroli_count
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
        "recent_activities": final_activities,
        "chart_data": chart_data,
        "tanggal": target_date.isoformat()
    }


@router.get("/map")
async def get_map_monitoring(
    kode_cabang: str = None,
    kode_dept: str = None,
    db: Session = Depends(get_db)
):
    # Get Last Known Location of Employees (Active only?)
    # Join EmployeeLocations with Karyawan and EmployeeStatus
    
    query = db.query(
        Karyawan.nik,
        Karyawan.nama_karyawan,
        Karyawan.kode_cabang,
        Karyawan.kode_dept,
        EmployeeLocations.latitude,
        EmployeeLocations.longitude,
        EmployeeLocations.updated_at,
        EmployeeStatus.is_online,
        EmployeeStatus.battery_level,
        EmployeeStatus.last_seen,
        Cabang.nama_cabang
    )\
        .join(EmployeeLocations, Karyawan.nik == EmployeeLocations.nik)\
        .outerjoin(EmployeeStatus, Karyawan.nik == EmployeeStatus.nik)\
        .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
        .filter(Karyawan.status_aktif_karyawan == '1')
        
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
        
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
        
    # Only show recent locations (e.g. last 24 hours)?
    # Or show all. Let frontend decide.
    # Usually show only if updated_at > today - 1 day
    yesterday_Limit = datetime.now() - timedelta(days=1)
    query = query.filter(EmployeeLocations.updated_at >= yesterday_Limit)
    
    locations = query.all()
    
    data = []
    for loc in locations:
        # Determine status color/icon based on last_seen
        # If last_seen < 15 mins ago -> Online (Green)
        # Else -> Offline (Gray)
        is_online = False
        if loc.last_seen:
             diff = datetime.now() - loc.last_seen
             if diff.total_seconds() < 900: # 15 mins
                 is_online = True
                 
        data.append({
            "nik": loc.nik,
            "nama": loc.nama_karyawan,
            "cabang": loc.nama_cabang,
            "dept": loc.kode_dept,
            "lat": float(loc.latitude) if loc.latitude else 0,
            "lng": float(loc.longitude) if loc.longitude else 0,
            "updated_at": str(loc.updated_at),
            "battery": loc.battery_level or 0,
            "status": "online" if is_online else "offline",
            "last_seen": str(loc.last_seen)
        })
        
    return {"status": True, "data": data}

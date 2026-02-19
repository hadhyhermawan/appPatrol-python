from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.models import Users
from app.routers import auth, auth_legacy, beranda_legacy, absensi_legacy, patroli_legacy, emergency_legacy, izin_legacy, logistik_legacy, task_legacy, berita_legacy, tracking_legacy, ops_legacy, tamu_legacy, barang_legacy, dashboard, monitoring, master, berita, security, utilities, payroll, chat_management, walkie_channel, general_setting, jam_kerja_dept, hari_libur, lembur, izin_absen, izin_sakit, izin_cuti, izin_dinas, employee_tracking, role_permission, statistik_legacy, surat_legacy, notifications

from fastapi.staticfiles import StaticFiles

import socketio
from app.sio import sio as sio_server

# Initialize FastAPI App
app_fastapi = FastAPI(
    title="Patrol & WorkGuard API (Python Migration)",
    description="Backend API migrated from Laravel/Node.js to Python FastAPI + Socket.IO",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Debug Middleware: Log all requests
@app_fastapi.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"DEBUG PATH: {request.method} {request.url.path}")
    response = await call_next(request)
    return response

# Mount Laravel Storage Public
app_fastapi.mount("/storage", StaticFiles(directory="/var/www/appPatrol/storage/app/public"), name="storage")
app_fastapi.mount("/api/storage", StaticFiles(directory="/var/www/appPatrol/storage/app/public"), name="api_storage")

# Mount Local Static (Python Only Storage)
import os
os.makedirs("/var/www/appPatrol-python/static/chat", exist_ok=True)
app_fastapi.mount("/static", StaticFiles(directory="/var/www/appPatrol-python/static"), name="static")
app_fastapi.mount("/api/static", StaticFiles(directory="/var/www/appPatrol-python/static"), name="api_static")

# Include Routers
app_fastapi.include_router(auth.router)
app_fastapi.include_router(auth_legacy.router) # Android Migration Endpoint
app_fastapi.include_router(beranda_legacy.router) # Android Migration Beranda
app_fastapi.include_router(absensi_legacy.router) # Android Migration Absensi
app_fastapi.include_router(patroli_legacy.router) # Android Migration Patroli
app_fastapi.include_router(emergency_legacy.router) # Android Migration Emergency
app_fastapi.include_router(izin_legacy.router) # Android Migration Izin
app_fastapi.include_router(logistik_legacy.router) # Android Migration Logistik
app_fastapi.include_router(task_legacy.router) # Android Migration Task
app_fastapi.include_router(berita_legacy.router) # Android Migration Berita
app_fastapi.include_router(tracking_legacy.router) # Android Migration Tracking
app_fastapi.include_router(ops_legacy.router) # Android Migration Ops (Briefing, Turlalin, Surat)
app_fastapi.include_router(tamu_legacy.router) # Android Migration Tamu (Moved from ops_legacy)
app_fastapi.include_router(barang_legacy.router) # Android Migration Barang
app_fastapi.include_router(dashboard.router)
app_fastapi.include_router(monitoring.router)
app_fastapi.include_router(master.router)
app_fastapi.include_router(berita.router)
app_fastapi.include_router(security.router)
app_fastapi.include_router(utilities.router)
app_fastapi.include_router(payroll.router)
app_fastapi.include_router(chat_management.router)
app_fastapi.include_router(walkie_channel.router)
app_fastapi.include_router(general_setting.router)
app_fastapi.include_router(jam_kerja_dept.router)
app_fastapi.include_router(hari_libur.router)
app_fastapi.include_router(hari_libur.router)
app_fastapi.include_router(lembur.router)
app_fastapi.include_router(notifications.router)
app_fastapi.include_router(izin_absen.router)
app_fastapi.include_router(izin_sakit.router)
app_fastapi.include_router(izin_cuti.router)
app_fastapi.include_router(izin_dinas.router)
app_fastapi.include_router(employee_tracking.router)
app_fastapi.include_router(role_permission.router)
app_fastapi.include_router(statistik_legacy.router)
app_fastapi.include_router(surat_legacy.router) # Android Migration Surat

from app.routers import laporan
app_fastapi.include_router(laporan.router) # Web Report Presensi

from app.routers import safety_briefing_legacy
app_fastapi.include_router(safety_briefing_legacy.router) # Android Migration Safety Briefing


from app.routers import verify_face_legacy
app_fastapi.include_router(verify_face_legacy.router)

from app.routers import jam_kerja_legacy
app_fastapi.include_router(jam_kerja_legacy.router) # Android Migration Jam Kerja Bulanan

from app.routers import master_wajah_legacy
app_fastapi.include_router(master_wajah_legacy.router) # Android Migration Master Wajah

from app.routers import monitoring_patrol_legacy
app_fastapi.include_router(monitoring_patrol_legacy.router) # Web Monitoring Patrol

from app.routers import monitoring_regu_legacy
app_fastapi.include_router(monitoring_regu_legacy.router) # Web Monitoring Regu (Legacy Logic)

from app.routers import violations
app_fastapi.include_router(violations.router) # Security Violations

from app.routers import walkie_legacy
app_fastapi.include_router(walkie_legacy.router) # Android Migration Walkie Channels
app_fastapi.include_router(walkie_legacy.router_node) # Node Backend Internal Endpoints

from app.routers import obrolan_legacy
app_fastapi.include_router(obrolan_legacy.router) # Android Chat Legacy

from app.routers import notifications
app_fastapi.include_router(notifications.router) # Notifications & Calls (FCM, Video)
@app_fastapi.get("/")
@app_fastapi.get("/api/")
def read_root():
    return {"message": "Hello from FastAPI!", "status": "online"}

@app_fastapi.get("/api/check-db")
def check_db(db: Session = Depends(get_db)):
    try:
        # Simple query to check connection
        user_count = db.query(Users).count()
        return {"status": "connected", "user_count": user_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Socket.IO Integration ---
# Wrap FastAPI with Socket.IO ASGI App
# socketio_path='/api/socket.io' matches Nginx rewrite: /api-py/socket.io -> /api/socket.io
app = socketio.ASGIApp(sio_server, app_fastapi, socketio_path='/api/socket.io')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

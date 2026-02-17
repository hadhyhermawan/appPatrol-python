from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.models import Users
from app.routers import auth, dashboard, monitoring, master, berita, security, utilities, payroll, chat_management, walkie_channel, general_setting, jam_kerja_dept, hari_libur, lembur, izin_absen, izin_sakit, izin_cuti, izin_dinas, employee_tracking, role_permission

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Patrol App Python Backend")

# Mount Laravel Storage Public
app.mount("/storage", StaticFiles(directory="/var/www/appPatrol/storage/app/public"), name="storage")

# Include Routers
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(monitoring.router)
app.include_router(master.router)
app.include_router(berita.router)
app.include_router(security.router)
app.include_router(utilities.router)
app.include_router(payroll.router)
app.include_router(chat_management.router)
app.include_router(walkie_channel.router)
app.include_router(general_setting.router)
app.include_router(jam_kerja_dept.router)
app.include_router(hari_libur.router)
app.include_router(lembur.router)
app.include_router(izin_absen.router)
app.include_router(izin_sakit.router)
app.include_router(izin_cuti.router)
app.include_router(izin_dinas.router)
app.include_router(employee_tracking.router)
app.include_router(role_permission.router)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI!"}

@app.get("/api/check-db")
def check_db(db: Session = Depends(get_db)):
    try:
        # Simple query to check connection
        user_count = db.query(Users).count()
        return {"status": "connected", "user_count": user_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

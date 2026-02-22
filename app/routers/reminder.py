"""
Reminder Settings CRUD
======================
Endpoint untuk admin mengelola konfigurasi reminder dari web backend.

Routes:
  GET    /api/reminder-settings         — Daftar semua setting
  POST   /api/reminder-settings         — Buat konfigurasi baru
  PUT    /api/reminder-settings/{id}    — Update konfigurasi
  DELETE /api/reminder-settings/{id}    — Hapus konfigurasi
  PATCH  /api/reminder-settings/{id}/toggle — Toggle aktif/nonaktif
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.models import ReminderSettings, Karyawan
from app.core.permissions import get_current_user
from app.core.fcm import _send_to_tokens

router = APIRouter(
    prefix="/api/reminder-settings",
    tags=["Reminder Settings"],
)

VALID_TYPES = {
    'absen_masuk', 'absen_pulang', 'absen_patroli',
    'cleaning_task', 'driver_task'
}

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ReminderCreate(BaseModel):
    type:           str
    label:          str
    message:        str
    minutes_before: int         = 30
    target_role:    Optional[str] = None
    target_dept:    Optional[str] = None
    target_cabang:  Optional[str] = None
    target_shift:   Optional[str] = None
    is_active:      int           = 1

class ReminderUpdate(BaseModel):
    label:          Optional[str] = None
    message:        Optional[str] = None
    minutes_before: Optional[int] = None
    target_role:    Optional[str] = None
    target_dept:    Optional[str] = None
    target_cabang:  Optional[str] = None
    target_shift:   Optional[str] = None
    is_active:      Optional[int] = None


def _to_dict(r: ReminderSettings) -> dict:
    return {
        "id":             r.id,
        "type":           r.type,
        "label":          r.label,
        "message":        r.message,
        "minutes_before": r.minutes_before,
        "target_role":    r.target_role,
        "target_dept":    r.target_dept,
        "target_cabang":  r.target_cabang,
        "target_shift":   r.target_shift,
        "is_active":      r.is_active,
        "created_at":     r.created_at.isoformat() if r.created_at else None,
        "updated_at":     r.updated_at.isoformat() if r.updated_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET: Daftar semua reminder settings
# ─────────────────────────────────────────────────────────────────────────────
@router.get("")
def list_reminders(db: Session = Depends(get_db)):
    rows = db.query(ReminderSettings).order_by(ReminderSettings.id).all()
    return {
        "status": True,
        "data": [_to_dict(r) for r in rows],
        "meta": {
            "valid_types": list(VALID_TYPES),
            "description": {
                "absen_masuk":   "Reminder sebelum jam masuk kerja",
                "absen_pulang":  "Reminder sebelum jam pulang kerja",
                "absen_patroli": "Reminder sebelum jadwal patroli mulai",
                "cleaning_task": "Reminder tugas cleaning service",
                "driver_task":   "Reminder tugas driver / perjalanan dinas",
            }
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST: Buat konfigurasi baru
# ─────────────────────────────────────────────────────────────────────────────
@router.post("")
def create_reminder(
    payload: ReminderCreate,
    db: Session = Depends(get_db)
):
    if payload.type not in VALID_TYPES:
        raise HTTPException(422, f"type harus salah satu dari: {VALID_TYPES}")
    if payload.minutes_before < 0 or payload.minutes_before > 480:
        raise HTTPException(422, "minutes_before harus antara 0–480")

    row = ReminderSettings(
        type=payload.type,
        label=payload.label,
        message=payload.message,
        minutes_before=payload.minutes_before,
        target_role=payload.target_role or None,
        target_dept=payload.target_dept or None,
        target_cabang=payload.target_cabang or None,
        target_shift=payload.target_shift or None,
        is_active=payload.is_active,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": True, "message": "Reminder berhasil dibuat", "data": _to_dict(row)}


# ─────────────────────────────────────────────────────────────────────────────
# PUT: Update konfigurasi
# ─────────────────────────────────────────────────────────────────────────────
@router.put("/{reminder_id}")
def update_reminder(
    reminder_id: int,
    payload: ReminderUpdate,
    db: Session = Depends(get_db)
):
    row = db.query(ReminderSettings).get(reminder_id)
    if not row:
        raise HTTPException(404, "Reminder tidak ditemukan")

    if payload.label          is not None: row.label          = payload.label
    if payload.message        is not None: row.message        = payload.message
    if payload.minutes_before is not None: row.minutes_before = payload.minutes_before
    if payload.target_role    is not None: row.target_role    = payload.target_role or None
    if payload.target_dept    is not None: row.target_dept    = payload.target_dept or None
    if payload.target_cabang  is not None: row.target_cabang  = payload.target_cabang or None
    if payload.target_shift   is not None: row.target_shift   = payload.target_shift or None
    if payload.is_active      is not None: row.is_active      = payload.is_active

    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    return {"status": True, "message": "Reminder berhasil diupdate", "data": _to_dict(row)}


# ─────────────────────────────────────────────────────────────────────────────
# DELETE: Hapus konfigurasi
# ─────────────────────────────────────────────────────────────────────────────
@router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db)
):
    row = db.query(ReminderSettings).get(reminder_id)
    if not row:
        raise HTTPException(404, "Reminder tidak ditemukan")
    db.delete(row)
    db.commit()
    return {"status": True, "message": "Reminder berhasil dihapus"}


# ─────────────────────────────────────────────────────────────────────────────
# PATCH: Toggle aktif / nonaktif
# ─────────────────────────────────────────────────────────────────────────────
@router.patch("/{reminder_id}/toggle")
def toggle_reminder(
    reminder_id: int,
    db: Session = Depends(get_db)
):
    row = db.query(ReminderSettings).get(reminder_id)
    if not row:
        raise HTTPException(404, "Reminder tidak ditemukan")
    row.is_active  = 0 if row.is_active else 1
    row.updated_at = datetime.now()
    db.commit()
    db.refresh(row)
    status_str = "diaktifkan" if row.is_active else "dinonaktifkan"
    return {"status": True, "message": f"Reminder {status_str}", "data": _to_dict(row)}


# ─────────────────────────────────────────────────────────────────────────────
# POST: Uji Kirim — kirim push notifikasi test untuk reminder ini sekarang
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{reminder_id}/test-send", dependencies=[Depends(get_current_user)])
def test_send_reminder(
    reminder_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    row = db.query(ReminderSettings).get(reminder_id)
    if not row:
        raise HTTPException(404, "Reminder tidak ditemukan")

    # Build query untuk ambil FCM token berdasarkan filter reminder
    q = db.execute(text("""
        SELECT DISTINCT kd.fcm_token
        FROM karyawan_devices kd
        JOIN karyawan k ON kd.nik = k.nik
        WHERE kd.fcm_token IS NOT NULL
          AND kd.fcm_token != ''
          AND (k.status_aktif_karyawan IS NULL OR k.status_aktif_karyawan = 1)
          AND (:target_role IS NULL OR k.kode_jabatan = :target_role OR k.kode_dept = :target_role)
          AND (:target_dept IS NULL OR k.kode_dept = :target_dept)
          AND (:target_cabang IS NULL OR k.kode_cabang = :target_cabang)
        LIMIT 200
    """), {
        "target_role":    row.target_role    or None,
        "target_dept":    row.target_dept    or None,
        "target_cabang":  row.target_cabang  or None,
    }).fetchall()

    tokens = list({r[0] for r in q if r[0]})

    if not tokens:
        # Fallback: kirim ke semua device jika tidak ada yang match
        fallback = db.execute(text("""
            SELECT DISTINCT fcm_token FROM karyawan_devices
            WHERE fcm_token IS NOT NULL AND fcm_token != ''
            LIMIT 200
        """)).fetchall()
        tokens = list({r[0] for r in fallback if r[0]})

    if not tokens:
        return {
            "status": False,
            "message": "Tidak ada device terdaftar untuk menerima notifikasi",
            "sent_to": 0
        }

    # Kirim FCM di background agar response tidak lama
    def do_send():
        result = _send_to_tokens(tokens, {
            "type":          "reminder",          # ← harus "reminder" agar Android mainkan suara
            "reminder_type": row.type,            # absen_masuk / absen_pulang / absen_patroli / dll
            "title":         f"🔔 {row.label}",
            "body":          row.message,
            "reminder_id":   str(row.id),
        })
        ok  = sum(1 for r in result if r.get("status") == 200)
        err = len(result) - ok
        print(f"[FCM TEST REMINDER] id={row.id} | sent={ok} | error={err}")

    background_tasks.add_task(do_send)

    return {
        "status": True,
        "message": f"Uji kirim dimulai ke {len(tokens)} device",
        "sent_to": len(tokens),
        "label":   row.label,
        "message_preview": row.message,
    }


"""
Auto Close Presensi — Lupa Absen Pulang
=========================================
Dijalankan setiap 5 menit oleh APScheduler.

Alur:
1. Ambil pengaturan: batas_jam_absen_pulang (dalam JAM)
2. Cari semua presensi: jam_in != null, jam_out = null, status != 'ta'
3. Hitung deadline = tanggal + jam_pulang + batas_jam_absen_pulang jam
   (handle lintas hari: tambah 1 hari jika lintashari=1)
4. Jika now_wib > deadline → update:
   - jam_out = deadline (waktu batas terakhir)
   - status  = 'ta'   (Tidak Absen / lupa absen pulang)
"""

import logging
from datetime import datetime, date, timedelta, time as dtime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.models import Presensi, PresensiJamkerja

logger = logging.getLogger("auto_close_presensi")

TZ_WIB = timezone(timedelta(hours=7))


def _get_pengaturan(db: Session) -> dict:
    """Ambil batas_jam_absen_pulang dari tabel pengaturan_umum."""
    try:
        from sqlalchemy import text
        row = db.execute(
            text("SELECT batas_jam_absen_pulang FROM pengaturan_umum LIMIT 1")
        ).fetchone()
        return {"batas_jam_absen_pulang": int(row[0]) if row else 3}
    except Exception as e:
        logger.warning(f"[AutoClose] Gagal ambil pengaturan: {e}")
        return {"batas_jam_absen_pulang": 3}


def run_auto_close_presensi():
    """
    Dijalankan setiap 5 menit.
    Tandai presensi 'ta' (lupa absen pulang) jika sudah melewati deadline.
    """
    db: Session = SessionLocal()
    try:
        now_wib = datetime.now(TZ_WIB)
        now     = now_wib.replace(tzinfo=None)   # naive untuk perbandingan
        today   = now.date()
        yesterday = today - timedelta(days=1)

        pengaturan = _get_pengaturan(db)
        batas_jam  = pengaturan["batas_jam_absen_pulang"]   # dalam JAM

        logger.info(
            f"[AutoClose] Tick {now.strftime('%Y-%m-%d %H:%M:%S')} WIB | "
            f"batas_jam_absen_pulang={batas_jam} jam"
        )

        # Ambil semua presensi yang belum pulang (hari ini atau kemarin lintas hari)
        kandidat = db.query(Presensi).filter(
            Presensi.jam_in  != None,
            Presensi.jam_out == None,
            Presensi.status  != 'ta',
            Presensi.tanggal.in_([today, yesterday])
        ).all()

        closed_count = 0
        for p in kandidat:
            try:
                # Ambil jam_pulang dari shift
                jk = db.query(PresensiJamkerja).filter(
                    PresensiJamkerja.kode_jam_kerja == p.kode_jam_kerja
                ).first()

                if not jk or not jk.jam_pulang:
                    continue

                # Hitung deadline: tanggal presensi + jam_pulang + batas jam
                base_date = p.tanggal  # date object
                jam_pulang_time = (
                    jk.jam_pulang
                    if isinstance(jk.jam_pulang, dtime)
                    else datetime.strptime(str(jk.jam_pulang), "%H:%M:%S").time()
                )

                end_dt = datetime.combine(base_date, jam_pulang_time)

                # Lintas hari: jam_pulang <= jam_masuk → selesai di hari berikutnya
                if jk.jam_masuk:
                    jam_masuk_time = (
                        jk.jam_masuk
                        if isinstance(jk.jam_masuk, dtime)
                        else datetime.strptime(str(jk.jam_masuk), "%H:%M:%S").time()
                    )
                    start_dt = datetime.combine(base_date, jam_masuk_time)
                    if end_dt <= start_dt:
                        end_dt += timedelta(days=1)

                # Tambah batas toleransi
                deadline = end_dt + timedelta(hours=batas_jam)

                if now > deadline:
                    # Tandai sebagai 'ta' — Tidak Absen Pulang
                    p.jam_out = None       # jam_out dikosongkan untuk menghindari rancu lembur
                    p.status  = 'ta'
                    db.add(p)
                    closed_count += 1
                    logger.info(
                        f"[AutoClose] NIK={p.nik} tanggal={p.tanggal} "
                        f"shift={p.kode_jam_kerja} | "
                        f"deadline={deadline.strftime('%Y-%m-%d %H:%M')} | "
                        f"→ status=ta, jam_out=None"
                    )

            except Exception as e:
                logger.error(f"[AutoClose] Error proses NIK={p.nik}: {e}")
                continue

        if closed_count:
            db.commit()
            logger.info(f"[AutoClose] ✅ {closed_count} presensi ditandai 'ta' (lupa absen pulang)")
        else:
            logger.debug("[AutoClose] Tidak ada presensi yang perlu ditutup.")

    except Exception as e:
        logger.error(f"[AutoClose] Fatal error: {e}")
        db.rollback()
    finally:
        db.close()

import re

code = """
        # Let's add Out of location push notification here:
        from app.models.models import Presensi
        from datetime import date
        today_date = date.today()
        # Check if user has active shift (jam_in exist but jam_out is NULL)
        active_session = db.query(Presensi).filter(
            Presensi.nik == user.nik, 
            Presensi.tanggal == today_date,
            Presensi.jam_in != None,
            Presensi.jam_out == None
        ).first()

        if active_session:
            karyawan_pelanggar = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
            if karyawan_pelanggar and karyawan_pelanggar.lock_location == '1':
                cabang_info = db.query(Cabang).filter(Cabang.kode_cabang == karyawan_pelanggar.kode_cabang).first()
                if cabang_info and cabang_info.lokasi_cabang and cabang_info.radius_cabang > 0:
                    try:
                        import math
                        clat, clon = map(float, cabang_info.lokasi_cabang.split(','))
                        dLat = math.radians(clat - latitude)
                        dLon = math.radians(clon - longitude)
                        a = math.sin(dLat/2) * math.sin(dLat/2) + \
                            math.cos(math.radians(latitude)) * math.cos(math.radians(clat)) * \
                            math.sin(dLon/2) * math.sin(dLon/2)
                        c_val = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                        dist = 6371000 * c_val
                        
                        if dist > cabang_info.radius_cabang:
                            # User is OUT OF LOCATION while ACTIVE!
                            satu_jam_lalu = datetime.now() - timedelta(hours=1)
                            from app.models.models import SecurityReports
                            recent_out_alert = db.query(SecurityReports).filter(
                                SecurityReports.nik == user.nik,
                                SecurityReports.type == 'OUT_OF_LOCATION',
                                SecurityReports.created_at >= satu_jam_lalu
                            ).first()

                            if not recent_out_alert:
                                target_karyawans = db.query(Karyawan.nik).filter(
                                    Karyawan.kode_cabang == karyawan_pelanggar.kode_cabang,
                                    Karyawan.nik != user.nik
                                ).all()
                                
                                target_niks = [r[0] for r in target_karyawans]
                                if target_niks:
                                    devices = db.query(KaryawanDevices).filter(KaryawanDevices.nik.in_(target_niks)).all()
                                    tokens = [d.fcm_token for d in devices if d.fcm_token]
                                    
                                    if tokens:
                                        nama_pelanggar = karyawan_pelanggar.nama_karyawan or user.nik
                                        nama_cabang = cabang_info.nama_cabang if cabang_info else "Cabang"

                                        alert_title = "⚠️ ANGGOTA KELUAR RADIUS"
                                        alert_body = f"Personel {nama_pelanggar} terdeteksi berada di luar jangkauan area {nama_cabang} saat jam bertugas."
                                        
                                        msg = messaging.MulticastMessage(
                                            notification=messaging.Notification(
                                                title=alert_title,
                                                body=alert_body
                                            ),
                                            data={
                                                "type": "SECURITY_ALERT",
                                                "subtype": "OUT_OF_LOCATION",
                                                "nik_pelanggar": user.nik,
                                                "nama_pelanggar": nama_pelanggar
                                            },
                                            tokens=tokens[:500],
                                            android=messaging.AndroidConfig(priority='high')
                                        )
                                        messaging.send_each_for_multicast(msg)
                                        print(f"OUT OF LOCATION ESCALATION SENT for NIK: {user.nik}")

                                # Catat ke security_reports
                                report = SecurityReports(
                                    type='OUT_OF_LOCATION',
                                    detail=f"Terdeteksi otomatis melalui modul Live Tracking. Jarak: {int(dist)}m dari maksimal {int(cabang_info.radius_cabang)}m",
                                    user_id=user.id,
                                    nik=user.nik,
                                    latitude=latitude,
                                    longitude=longitude,
                                    status_flag='pending',
                                    created_at=datetime.now(),
                                    updated_at=datetime.now()
                                )
                                db.add(report)
                                db.commit()
                    except Exception as err:
                        print(f"Failed handling OUT_OF_LOCATION concern: {err}")
"""
print("OK")

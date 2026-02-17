
# --------------------------------------------------------------------------------------
# NEW TOGGLE ENDPOINTS
# --------------------------------------------------------------------------------------

@router.patch("/karyawan/{nik}/toggle/location")
async def toggle_location(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Toggle lock_location ('1' -> '0', '0' -> '1')
        new_val = '0' if karyawan.lock_location == '1' else '1'
        karyawan.lock_location = new_val
        db.commit()
        db.refresh(karyawan)
        
        return {"status": True, "message": f"Lock Location updated to {new_val}", "data": new_val}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/karyawan/{nik}/toggle/jamkerja")
async def toggle_jamkerja(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Toggle lock_jam_kerja
        new_val = '0' if karyawan.lock_jam_kerja == '1' else '1'
        karyawan.lock_jam_kerja = new_val
        db.commit()
        
        return {"status": True, "message": f"Lock Jam Kerja updated to {new_val}", "data": new_val}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/karyawan/{nik}/toggle/device")
async def toggle_device(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Toggle lock_device_login
        new_val = '0' if karyawan.lock_device_login == '1' else '1'
        karyawan.lock_device_login = new_val
        db.commit()
        
        # In Laravel, this also deletes tokens. In JWT stateless, we can't easily delete issued tokens
        # unless stored/blacklisted. For now, we just update the flag.
        
        return {"status": True, "message": f"Lock Device updated to {new_val}", "data": new_val}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/karyawan/{nik}/toggle/multidevice")
async def toggle_multidevice(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Toggle allow_multi_device
        new_val = '0' if karyawan.allow_multi_device == '1' else '1'
        karyawan.allow_multi_device = new_val
        db.commit()
        
        return {"status": True, "message": f"Allow Multi Device updated to {new_val}", "data": new_val}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/karyawan/{nik}/reset-session")
async def reset_session(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # 1. Reset lock device to 0 (unlocked)
        karyawan.lock_device_login = '0'
        
        # 2. Force logout logic (User tokens)
        # Check if user exists for this nik
        # user_karyawan = db.query(UserKaryawan).filter(UserKaryawan.nik == nik).first()
        # if user_karyawan:
             # Logic to invalidate tokens for user_karyawan.id_user
             # Since we don't have token storage shown, we skip actual token deletion for now.
        
        db.commit()
        
        return {"status": True, "message": "Sesi berhasil direset (Lock Device dibuka)."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

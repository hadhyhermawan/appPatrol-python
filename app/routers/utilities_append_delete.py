
# In app/routers/utilities.py

@router.delete("/multi-device/logs")
async def delete_multi_device_logs(
    user_id: int,
    device: str,
    db: Session = Depends(get_db)
):
    try:
        # Delete all login logs for this user with this device
        db.query(LoginLogs).filter(
            LoginLogs.user_id == user_id,
            LoginLogs.device == device
        ).delete(synchronize_session=False)

        # Also, we should probably check if it's in karyawan_devices and delete it too to fully clear it?
        # Let's check if the user wants just logs or full cleanup. Usually full.
        # But this report is strictly LoginLogs based.
        # Let's check models for correct user link.
        # LoginLogs.user_id links to users.id. 
        # KaryawanDevices usually links via NIK.
        
        # Let's find the NIK from User first.
        # This is a bit complex due to missing relationship definitions in models (as noted in prior steps).
        # We'll stick to LoginLogs for now as that drives the report.

        db.commit()
        return {"message": "Device logs deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

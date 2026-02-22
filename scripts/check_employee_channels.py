from app.database import SessionLocal
from app.models.models import Karyawan, KaryawanDevices, WalkieChannels, WalkieChannelCabangs
from sqlalchemy import or_

db = SessionLocal()

niks = ["1801042008930002", "1801042008930003"]

print(f"--- Checking Employees: {niks} ---")

employees = db.query(Karyawan).filter(Karyawan.nik.in_(niks)).all()

if not employees:
    print("No employees found with these NIKs.")
else:
    for emp in employees:
        print(f"\nEmployee: {emp.nama_karyawan} ({emp.nik})")
        print(f"  Cabang: {emp.kode_cabang}")
        print(f"  Dept: {emp.kode_dept}")
        
        # Check FCM Token
        device = db.query(KaryawanDevices).filter(KaryawanDevices.nik == emp.nik).first()
        token_status = "✅ Present" if device and device.fcm_token else "❌ Missing"
        print(f"  FCM Token: {token_status}")
        if device:
            print(f"  Token Preview: {device.fcm_token[:20]}..." if device.fcm_token else "  Token is None")

        # Check Accessible Channels
        print("  Accessible Channels:")
        
        # 1. By Cabang
        channels_by_cabang = db.query(WalkieChannels).join(WalkieChannelCabangs).filter(
            WalkieChannelCabangs.kode_cabang == emp.kode_cabang
        ).all()
        
        # 2. By Dept (Checking comma separated string in dept_members)
        # simplified check, getting all channels first
        all_channels = db.query(WalkieChannels).all()
        channels_by_dept = []
        for ch in all_channels:
            if ch.dept_members and emp.kode_dept in ch.dept_members.split(','):
                channels_by_dept.append(ch)
                
        found_channels = set(channels_by_cabang + channels_by_dept)
        
        if not found_channels:
            print("    ❌ No channels found for this user.")
        else:
            for ch in found_channels:
                 print(f"    - {ch.name} (Code: {ch.code})")

print("\n--- End Check ---")

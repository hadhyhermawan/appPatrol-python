#!/usr/bin/env python3
import sys
import os

# Adds the project root to the path so we can import 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal

# Map groups to their permissions
PERMISSION_MAP = {
    "Master Data": [
        "departemen", "jabatan", "cabang", "cuti", "jamkerja", 
        "jadwal", "karyawan", "patrolpoint", "walkiechannel", "depttaskpoint"
    ],
    "Security Patrol": [
        "giatpatrol", "tamu", "barang", "turlalin", "surat", 
        "tracking", "safety", "monitoringpatrol"
    ],
    "Presensi & Waktu": [
        "presensi", "lembur", "izin"
    ],
    "Payroll": [
        "gajipokok", "tunjangan", "jenistunjangan", "penyesuaiangaji", 
        "bpjskesehatan", "bpjstenagakerja", "slipgaji"
    ],
    "Cleaning": [
        "cleaning"
    ],
    "Laporan": [
        "laporan"
    ],
    "Settings": [
        "generalsetting", "harilibur", "jamkerjadepartemen"
    ],
    "System Utilities": [
        "users", "roles", "permissions", "permissiongroups", 
        "logs", "multidevice", "chat"
    ]
}

def seed_permissions():
    db = SessionLocal()
    
    try:
        print("🌱 Starting Seed Permissions into Database...")
        
        for group_name, modules in PERMISSION_MAP.items():
            # 1. Ensure Permission Group Exists
            group = db.execute(
                text("SELECT id FROM permission_groups WHERE name = :name"),
                {"name": group_name}
            ).fetchone()
            
            if not group:
                db.execute(
                    text("INSERT INTO permission_groups (name, created_at, updated_at) VALUES (:name, NOW(), NOW())"),
                    {"name": group_name}
                )
                db.commit()
                group = db.execute(
                    text("SELECT id FROM permission_groups WHERE name = :name"),
                    {"name": group_name}
                ).fetchone()
                print(f"Created Group: {group_name}")
            
            group_id = group[0]
            
            # 2. Add permissions for each module in the group
            for module in modules:
                # Add CRUD permissions
                for action in ["index", "create", "update", "delete", "show"]:
                    # Specific to laporan actions
                    if module == "laporan" and action not in ["index", "presensi"]:
                        continue # Reports mostly have index or view specific
                    
                    if module == "laporan" and action == "index":
                        perm_name = "laporan.index"
                    elif module == "laporan" and action == "presensi":
                        perm_name = "laporan.presensi"
                    else:
                        perm_name = f"{module}.{action}"
                        
                    # Check if permission exists
                    perm = db.execute(
                        text("SELECT id FROM permissions WHERE name = :name"),
                        {"name": perm_name}
                    ).fetchone()
                    
                    if not perm:
                        db.execute(
                            text("INSERT INTO permissions (name, guard_name, id_permission_group, created_at, updated_at) VALUES (:name, 'web', :group_id, NOW(), NOW())"),
                            {"name": perm_name, "group_id": group_id}
                        )
                        print(f"  + Added Permission: {perm_name}")
                        
        db.commit()
        
        # 3. Ensure Super Admin role has all permissions
        super_admin = db.execute(
            text("SELECT id FROM roles WHERE id = 1")
        ).fetchone()
        
        if super_admin:
            db.execute(text("""
                INSERT IGNORE INTO role_has_permissions (permission_id, role_id)
                SELECT id, 1 FROM permissions
            """))
            db.commit()
            print("\n👑 Granted all permissions to Super Admin")

        print("\n✅ Seed Permissions Completed!")
        
    except Exception as e:
        print(f"Error seeding permissions: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_permissions()

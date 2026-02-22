from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
import shutil
import os
import uuid

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import Tamu, Barang, BarangMasuk, BarangKeluar

router = APIRouter(
    prefix="/api/android",
    tags=["Logistik Legacy"],
)

STORAGE_TAMU = "/var/www/appPatrol/storage/app/public/tamu"
STORAGE_BARANG = "/var/www/appPatrol/storage/app/public/barang"
os.makedirs(STORAGE_TAMU, exist_ok=True)
os.makedirs(STORAGE_BARANG, exist_ok=True)

# Endpoint Tamu sudah dipindah ke tamu_legacy.py

# --- BARANG ---
# MOVED TO app/routers/barang_legacy.py

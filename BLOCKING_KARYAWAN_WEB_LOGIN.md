# 🔒 Blocking Role "Karyawan" dari Web Backend

**Tanggal:** 2026-02-17 15:55  
**Database:** patrol  
**Backend:** Python FastAPI

---

## 📋 Ringkasan

Role **"karyawan"** (227 users) sekarang **DIBLOKIR** dari login ke web backend. Mereka hanya bisa menggunakan **aplikasi mobile**.

---

## 🎯 Implementasi

### File yang Dimodifikasi:
**`/var/www/appPatrol-python/app/routers/auth.py`**

### Perubahan:
Menambahkan pengecekan role setelah password verification:

```python
# 3. Check if user has 'karyawan' role - they cannot login to web backend
user_roles = db.execute(
    text("""
        SELECT r.name 
        FROM model_has_roles mhr
        JOIN roles r ON mhr.role_id = r.id
        WHERE mhr.model_id = :user_id 
        AND mhr.model_type = 'App\\\\Models\\\\User'
    """),
    {"user_id": user.id}
).fetchall()

role_names = [row[0] for row in user_roles]

# Block karyawan role from web login
if 'karyawan' in role_names and len(role_names) == 1:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Akses ditolak. Role 'karyawan' hanya dapat menggunakan aplikasi mobile.",
    )
```

---

## 🔍 Logic Pengecekan

### Kondisi Blocking:
User akan **DIBLOKIR** jika:
1. ✅ Memiliki role "karyawan"
2. ✅ **HANYA** memiliki role "karyawan" (tidak punya role lain)

### Kondisi Allowed:
User akan **DIIZINKAN** jika:
1. ✅ Tidak memiliki role "karyawan"
2. ✅ Memiliki role "karyawan" **DAN** role lain (misal: "karyawan" + "super admin")

---

## 📊 Data Role "Karyawan"

### Total Users: **227**

### Permissions yang Dimiliki (26 permissions):
Semua permission untuk **mobile app only**:

**Presensi:**
- presensi.create
- presensi.delete
- presensi.edit
- presensi.index

**Izin Absen:**
- izinabsen.create
- izinabsen.delete
- izinabsen.edit
- izinabsen.index

**Izin Cuti:**
- izincuti.create
- izincuti.delete
- izincuti.edit
- izincuti.index

**Izin Dinas:**
- izindinas.create
- izindinas.delete

**Izin Sakit:**
- izinsakit.create
- izinsakit.delete
- izinsakit.edit
- izinsakit.index

**Lembur:**
- lembur.create
- lembur.delete
- lembur.edit
- lembur.index

**Patrol:**
- giatpatrol.create
- giatpatrol.index
- giatpatrol.update

**Slip Gaji:**
- slipgaji.index

---

## 🚫 Response Error

### HTTP Status Code:
**403 Forbidden**

### Error Message:
```json
{
  "detail": "Akses ditolak. Role 'karyawan' hanya dapat menggunakan aplikasi mobile."
}
```

---

## ✅ Testing

### Test Case 1: User dengan role "karyawan" saja
**Expected:** ❌ Login DITOLAK dengan error 403

```bash
curl -X POST https://frontend.k3guard.com/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "nama_karyawan",
    "password": "password123"
  }'
```

**Response:**
```json
{
  "detail": "Akses ditolak. Role 'karyawan' hanya dapat menggunakan aplikasi mobile."
}
```

---

### Test Case 2: User dengan role "super admin"
**Expected:** ✅ Login BERHASIL

```bash
curl -X POST https://frontend.k3guard.com/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "password123"
  }'
```

**Response:**
```json
{
  "message": "Login berhasil",
  "token": "eyJ...",
  "data": {...}
}
```

---

### Test Case 3: User dengan multiple roles (karyawan + admin)
**Expected:** ✅ Login BERHASIL (karena punya role lain selain karyawan)

---

## 📝 Catatan Penting

1. **Mobile App Tidak Terpengaruh**
   - Karyawan tetap bisa login via mobile app
   - Blocking hanya berlaku untuk web backend

2. **Dual Role Users**
   - Jika user punya role "karyawan" + role lain, mereka tetap bisa login web
   - Contoh: User dengan role ["karyawan", "admin departemen"] → ALLOWED

3. **Permission Check**
   - Blocking dilakukan di level authentication (login)
   - Tidak perlu ubah permission karena karyawan memang tidak punya permission untuk dashboard

4. **Database**
   - Tidak ada perubahan di database
   - Hanya logic di backend yang ditambahkan

---

## 🔄 Rollback

Jika perlu rollback, hapus code block di `/var/www/appPatrol-python/app/routers/auth.py` baris 47-66:

```bash
# Hapus section "# 3. Check if user has 'karyawan' role..."
# Kemudian restart backend
pm2 restart patrol-backend
```

---

## 📊 Impact Analysis

### Affected Users: **227 karyawan**
- ❌ Tidak bisa login web backend lagi
- ✅ Tetap bisa login mobile app
- ✅ Semua fitur mobile tetap berfungsi normal

### Unaffected Users:
- ✅ Super admin (1 user)
- ✅ Admin departemen (2 users)
- ✅ Unit pelaksana pelayanan pelanggan (6 users)
- ✅ Unit layanan pelanggan (7 users)

---

## ✅ Status

- ✅ Code implemented
- ✅ Backend restarted (patrol-backend)
- ✅ Ready for testing
- ✅ **ACTIVE**

---

**Modified by:** AI Assistant  
**Approved by:** User  
**Deployed:** 2026-02-17 15:56

import requests
import json

app_url = "http://127.0.0.1:8000"

login_data = {
    "username": "1801042008930002",
    "password": "1801042008930002",
    "device_id": "test"
}
login_url = f"{app_url}/api/android/auth/login"
r = requests.post(login_url, data=login_data)
if r.status_code != 200:
    print("Login fail:", r.status_code, r.text)
    exit(1)

token = r.json().get("data", {}).get("access_token")

tamu_url = f"{app_url}/api/android/tamu/store"
headers = {"Authorization": f"Bearer {token}"}
data = {
    "nama": "TEST",
    "alamat": "Mars",
    "jenis_id": "KTP",
    "no_telp": "089999999",
    "perusahaan": "SpaceX",
    "bertemu_dengan": "Musk",
    "dengan_perjanjian": "TIDAK",
    "keperluan": "Invasion",
    "jenis_kendaraan": "RODA 2",
    "no_pol": "B 1234 CD",
}
files = {"foto": ("fake.jpg", b"123", "image/jpeg")}

r2 = requests.post(tamu_url, headers=headers, data=data, files=files)
print("Create tamu:", r2.status_code, r2.text)

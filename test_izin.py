import requests

url = "http://localhost:8000/api/android/login"
data = {"username": "1801042008930002", "password": "password", "device_id": "test"}
r = requests.post(url, json=data)
print("LOGIN REPONSE:")
print(r.text)
try:
    token = r.json().get('token')
except:
    token = None

if token:
    url2 = "http://localhost:8000/api/android/izin-absen/store"
    headers = {"Authorization": f"Bearer {token}"}
    data2 = {"dari": "2024-03-01", "sampai": "2024-03-02", "keterangan": "sakit"}
    r2 = requests.post(url2, headers=headers, data=data2)

    print("--- POST RESULT ---")
    print(r2.status_code)
    print(r2.text)


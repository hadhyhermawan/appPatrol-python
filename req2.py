import requests

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyNTIiLCJ1c2VybmFtZSI6IjE4MDEwMzIwMDg5MzAwMDQiLCJleHAiOjE3Nzk1MzU4NTAsImlhdCI6MTc3MTc1OTg1MCwic2NvcGUiOiJhbmRyb2lkIn0.Z9-ZsWdaSVgLvznlyjv_ONd9RaOxbCiN4isp0O-McW8"
files = {'image': open('/var/www/appPatrol-python/docs/placeholder.png', 'rb')}
data = {'status': 'masuk', 'lokasi': '-6.20, 106.81'}
headers = {"Authorization": f"Bearer {TOKEN}"}

resp = requests.post("http://localhost:8000/api/android/absensi/absen", data=data, files=files, headers=headers)
print(resp.status_code)
print(resp.text)

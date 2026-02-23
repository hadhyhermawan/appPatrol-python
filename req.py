import requests
resp = requests.post("http://localhost:8000/api/android/login", data={"username": "1801032008930004", "password": "1801032008930004"})
print(resp.status_code)
print(resp.json())

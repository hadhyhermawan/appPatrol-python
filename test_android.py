import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

# Login to get token
login_data = {
    "username": "1801042008930002",
    "password": "1801042008930002",
    "device_model": "SAMSUNG SM-G998B",
    "app_version": "1.0.0",
    "include_walkie_channels": 1
}

print("Attempting login...")
resp = requests.post(f"{BASE_URL}/android/login", data=login_data, headers={"X-App-Version": "1.0.0"})
if resp.status_code != 200:
    print(f"Login failed: {resp.status_code} {resp.text}")
    exit(1)

token = resp.json().get("token")
print(f"Login successful, got token.")

headers = {
    "Authorization": f"Bearer {token}",
    "X-App-Version": "1.0.0"
}

# Simulate Force Close
print("\nSubmitting APP_FORCE_CLOSE report...")
abuse_data_1 = {
    "type": "APP_FORCE_CLOSE",
    "detail": "Test Force Close from Script",
    "device_model": "SAMSUNG SM-G998B",
    "device_id": "test_device_id_123",
    "nik": "1801042008930002",
    "lat": -6.200000,
    "lon": 106.816666
}

resp_abuse = requests.post(f"{BASE_URL}/android/security/report-abuse", data=abuse_data_1, headers=headers)
print(f"Force Close Resp: {resp_abuse.status_code} {resp_abuse.text}")

# Now let's test location update which triggers Mock Location / Out of Location tracking alerts
print("\nSubmitting Location Update with Mock Location=1 (FAKE_GPS)...")
loc_data_mock = {
    "latitude": -6.200000,
    "longitude": 106.816666,
    "accuracy": 10.0,
    "speed": 0.0,
    "bearing": 0.0,
    "provider": "gps",
    "isMocked": 1,
    "batteryLevel": 80,
    "isCharging": 0
}

resp_loc = requests.post(f"{BASE_URL}/android/tracking/location", data=loc_data_mock, headers=headers)
print(f"Location Update (Mock) Resp: {resp_loc.status_code} {resp_loc.text}")

print("\nSubmitting Location Update out of bounds (OUT_OF_LOCATION)...")
loc_data_out = {
    "latitude": -6.500000, # Far away
    "longitude": 106.816666,
    "accuracy": 10.0,
    "speed": 0.0,
    "bearing": 0.0,
    "provider": "gps",
    "isMocked": 0,
    "batteryLevel": 80,
    "isCharging": 0
}

resp_loc2 = requests.post(f"{BASE_URL}/android/tracking/location", data=loc_data_out, headers=headers)
print(f"Location Update (Out of Bounds) Resp: {resp_loc2.status_code} {resp_loc2.text}")

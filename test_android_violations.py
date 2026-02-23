import requests
import json

base_url = "http://localhost:8000"

# 1. Login
login_url = f"{base_url}/api/android/login"
login_data = {
    "username": "1801032008930004",
    "password": "1801032008930004",  # Using username as password if default applies, otherwise we will see
    "device_model": "Test",
    "android_version": "13"
}
headers = {
    "X-App-Version": "1.0.0"
}

print(f"Logging in to {login_url}")
response = requests.post(login_url, data=login_data, headers=headers)

if response.status_code == 200:
    token = response.json().get("token")
    print(f"Login successful! Token: {token[:20]}...")
    
    # 2. Get Violations
    violations_url = f"{base_url}/api/android/violations/my"
    auth_headers = {
        "Authorization": f"Bearer {token}"
    }
    
    print("\nFetching violations...")
    v_resp = requests.get(violations_url, headers=auth_headers)
    print(f"Status Code: {v_resp.status_code}")
    
    try:
        print(json.dumps(v_resp.json(), indent=2))
    except Exception as e:
        print(f"Parse error: {e}, Text: {v_resp.text}")
        
else:
    print(f"Login failed! Status: {response.status_code}")
    print(response.text)

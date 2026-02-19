import requests
import json
import sys

# Configuration
BASE_URL = "http://127.0.0.1:8000/api"  # Assuming backend runs on port 8000 locally
USERNAME = "admin"
PASSWORD = "ktbpjk3l#876543"
TARGET_NIK = "1801042008930003"

def login():
    url = f"{BASE_URL}/login"
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "device_model": "Script",
        "android_version": "Script"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Login failed: {e}")
        if response:
            print(f"Response: {response.text}")
        sys.exit(1)

def reset_session(token):
    url = f"{BASE_URL}/master/karyawan/{TARGET_NIK}/reset-session"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Reset session failed: {e}")
        if response:
            print(f"Response: {response.text}")
        sys.exit(1)

def main():
    print(f"1. Logging in as {USERNAME}...")
    auth_data = login()
    token = auth_data.get("access_token")
    if not token:
        print("Failed to get access token")
        sys.exit(1)
    print("   Login successful.")

    print(f"2. Triggering Reset Session for NIK {TARGET_NIK}...")
    result = reset_session(token)
    print("   Reset Session Result:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

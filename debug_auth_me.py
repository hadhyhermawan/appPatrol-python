import requests
import json
import sys

# Configuration
BASE_URL = "http://127.0.0.1:8000/api"
USERNAME = "admin"
PASSWORD = "ktbpjk3l#876543"

def debug_auth_me():
    try:
        # STEP 1: LOGIN
        login_url = f"{BASE_URL}/login"
        payload = {"username": USERNAME, "password": PASSWORD}
        headers = {"Content-Type": "application/json"}
        
        print(f"Logging in as {USERNAME}...")
        response = requests.post(login_url, json=payload, headers=headers)
        
        if response.status_code != 200:
            print(f"Login failed: {response.status_code}")
            print(response.text)
            return

        login_data = response.json()
        token = login_data.get("token")
        if not token:
            print("No token received!")
            return
            
        print("Login successful. Token received.")

        # STEP 2: GET AUTH ME
        me_url = f"{BASE_URL}/auth/me"
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        print(f"Fetching {me_url}...")
        me_response = requests.get(me_url, headers=auth_headers)
        
        if me_response.status_code == 200:
            me_data = me_response.json()
            print("\n--- RESPONSE FROM /auth/me ---")
            print(json.dumps(me_data, indent=2))
            
            # Focus on roles
            roles = me_data.get("roles", [])
            print(f"\nRoles found: {len(roles)}")
            for role in roles:
                print(f"- ID: {role.get('id')}, Name: '{role.get('name')}'")
                
            # Check for permissions
            perms = me_data.get("permissions", [])
            print(f"Permissions count: {len(perms)}")
            
        else:
            print(f"Failed to fetch /auth/me: {me_response.status_code}")
            print(me_response.text)

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    debug_auth_me()

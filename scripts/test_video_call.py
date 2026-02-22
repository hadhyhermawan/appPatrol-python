import urllib.request
import json

TOKEN = "4467|qLnJBstWJE4wvGR0XXv6xI2kzzhE6IENQQaCl9ZH3a8c5c2b"
URL = "http://127.0.0.1:8000/api/video-call/start"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

payload = {
    "room_id": "UID001",
    "caller_name": "Test Script"
}

try:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(URL, data=data, headers=headers, method='POST')

    print(f"Sending POST to {URL}...")
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        print(f"Response: {response.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
